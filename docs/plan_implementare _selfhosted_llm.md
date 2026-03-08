---
id: PLAN-002
title: Implementare Infrastructură AI Self-Hosted (Hetzner bare-metal, vLLM)
doc_class: runbook
domain: ai-infrastructure
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: platform_architecture_lead
tags: [plan, ai-infrastructure, vllm, hetzner, wave-1]
---

PROMPT DE IMPLEMENTARE ENTERPRISE-GRADE: INFRASTRUCTURĂ AI LOCALĂ (MARTIE 2026)CĂTRE: Agent AI de Autonomizare / Senior DevOps EngineerOBIECTIV: Trecerea serverului bare-metal (aflat în Hetzner Rescue Mode) într-un nod de inferență AI de înaltă performanță, integrat în Hetzner vSwitch, rulând simultan un model avansat de reasoning (Qwen3.5-QwQ-32B) și Qwen3.5-9B via vLLM.DATA CURENTĂ: Martie 2026FAZA 0: CONTEXT ARHITECTURAL ȘI DECIZII TEHNICE (BRIEFING PENTRU AGENT)Agent, înainte de a rula orice comandă, trebuie să asimilezi următorul context tehnologic și constatările supercritice care au fundamentat achiziția acestui hardware:Hardware Țintă (Hetzner Auction ID: 2936089):CPU: Intel Xeon Gold 5412U (24 Cores / 48 Threads)RAM: 256 GB DDR5 ECC (8 x 32GB)Storage: 2 x 1.92 TB U.2 NVMe Datacenter SSDGPU: 1 x NVIDIA RTX 6000 Ada Generation (48 GB GDDR6 ECC VRAM)Rețea Publică: 1 Gbit (Locație: NBG1-DC6)Rețea Internă (vSwitch): Serverul face parte dintr-un cluster privat conectat prin Hetzner vSwitch. Resursele AI trebuie expuse doar către acest subnet intern.Politică de Zero-Impact (Atașare la Clusterul Existent):REGULĂ STRICTĂ: Orice configurare de rețea, sistem sau firewall efectuată pe acest server trebuie să fie strict locală.Scopul este anexarea acestui nod la clusterul existent fără a perturba în niciun fel rutele, gateway-urile, politicile DNS sau serviciile celorlalte mașini.Nu se vor emite broadcast-uri nedorite, nu se va rula niciun serviciu DHCP/DNS pe interfața vSwitch și se va evita orice conflict de IP. Serverul este doar un simplu "worker" (furnizor de API-uri AI) pentru restul rețelei.Topologia Modelelor AI (Seria Qwen 3.5 / R1 Distill - Martie 2026):S-a renunțat la rularea Kimi K2.5 (1T parametri, MoE) din cauza latenței severe.Decizia Enterprise: Rularea unui setup dual pe același GPU.Model Principal (Heavy Duty / Reasoning): Qwen3.5-QwQ-32B (varianta nativă de reasoning a seriei 3.5) sau DeepSeek-R1-Distill-Qwen-32B. Va utiliza ~20-24 GB VRAM (în format FP8 / AWQ).Model Secundar (Fast Responder): Qwen3.5-9B-Instruct. Va utiliza ~8-10 GB VRAM. Lăsând restul de ~14-20 GB pentru context vizual mare (128K+) și KV Cache.Standarde de Implementare: Se va folosi Ubuntu 24.04 LTS, drivere NVIDIA Enterprise (550+), CUDA Toolkit SOTA, vLLM ca backend de inferență (optimizat cu FlashAttention-3) și Open WebUI.FAZA 1: BARE-METAL PROVISIONING (HETZNER RESCUE MODE)Agent, ești conectat prin SSH în Hetzner Rescue Mode (Debian-based RAM disk). Execută următoarele pentru a instala OS-ul pe disk-urile fizice.1.1. Configurarea installimageVom folosi un setup RAID 1 (Software) pentru redundanță enterprise pe cele două unități NVMe U.2.Crează un fișier de configurare /install.conf:cat << 'EOF' > /install.conf
DRIVE1 /dev/nvme0n1
DRIVE2 /dev/nvme1n1
SWRAID 1
SWRAIDLEVEL 1
BOOTLOADER grub
HOSTNAME ai-node-enterprise
PART /boot ext3 1024M
PART lvm vg0 all
LV vg0 root / ext4 200G
LV vg0 swap swap 32G
LV vg0 data /data ext4 all
IMAGE /root/.oldroot/nfs/install/../images/Ubuntu-2404-noble-amd64-base.tar.gz
EOF
1.2. Execuția Instalării și Rebootinstallimage -a -c /install.conf
reboot
Așteaptă reboot-ul. Reconectează-te pe noua instanță Ubuntu 24.04 LTS.FAZA 2: OS TUNING ȘI HARDWARE OPTIMIZATIONSistemul necesită tuning specific pentru o mașină cu Xeon Gold și NVMe U.2 pentru a elimina bottleneck-urile I/O și CPU către GPU.2.1. Update, Upgrade și Dependențe Coreapt update && apt upgrade -y
apt install -y build-essential dkms curl wget git htop iotop nvme-cli linux-headers-$(uname -r) software-properties-common fail2ban ufw vlan
2.2. Tuning Kernel & CPUOptimizează performanța procesorului Xeon și crește limitele sistemului pentru backend-ul AI.# Set CPU governor to performance
echo "performance" | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Creșterea ulimits pentru file descriptors
cat << 'EOF' >> /etc/security/limits.conf
* soft nofile 1048576
* hard nofile 1048576
root soft nofile 1048576
root hard nofile 1048576
EOF

# Aplicare sysctl tuning local
cat << 'EOF' >> /etc/sysctl.conf
vm.max_map_count=262144
vm.swappiness=10
net.ipv4.tcp_fastopen=3
net.core.somaxconn=65535
EOF
sysctl -p
2.3. Configurare Rețea Privată (Hetzner vSwitch) - FĂRĂ IMPACT EXTERNAgent: Identifică interfața principală (ex. enp3s0), VLAN ID-ul alocat și un IP liber care NU intră în conflict cu celelalte servere din cluster. Adaptează Netplan DOAR pentru acest nod.# Exemplu Netplan.
# ATENȚIE AGENT: NU seta `gateway4`, `routes` default sau servere DNS personalizate
# pe interfața VLAN pentru a nu altera tabela de rutare a mașinii sau a clusterului.
# Rutarea principală către internet rămâne exclusiv pe interfața publică implicită.

cat << 'EOF' > /etc/netplan/02-vswitch.yaml
network:
  version: 2
  vlans:
    vlan.4000:
      id: 4000
      link: enp3s0 # Interfața fizică principală
      addresses:
        - 10.0.0.5/24 # IP-ul strict dedicat acestui server AI (fără conflict)
EOF

netplan apply
FAZA 3: INFRASTRUCTURA NVIDIA (DRIVER, CUDA & DOCKER)3.1. Instalare Driver NVIDIA (Proprietary / Enterprise)add-apt-repository ppa:graphics-drivers/ppa -y
apt update
apt install -y nvidia-driver-550-server nvidia-utils-550-server
3.2. Instalare Docker & NVIDIA Container Toolkitcurl -fsSL [https://get.docker.com](https://get.docker.com) -o get-docker.sh
sh get-docker.sh

curl -fsSL [https://nvidia.github.io/libnvidia-container/gpgkey](https://nvidia.github.io/libnvidia-container/gpgkey) | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L [https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list](https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list) | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt update
apt install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
3.3. GPU Tuning (Persistență și Limite)nvidia-smi -pm 1
nvidia-smi -q -d MEMORY,ECC
FAZA 4: BOOTSTRAPPING BACKEND AI (VLLM DUAL-MODEL ARCHITECTURE)4.1. Structura Directoarelormkdir -p /data/ai-infrastructure/{models,config,webui}
cd /data/ai-infrastructure
4.2. Generarea docker-compose.ymlversion: '3.8'

services:
  # Model Principal: Qwen3.5-QwQ-32B (Reasoning Model Optimizat AWQ/FP8)
  vllm-primary:
    image: vllm/vllm-openai:latest
    container_name: vllm-qwq-32b
    runtime: nvidia
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    ports:
      - "8000:8000"
    volumes:
      - /data/ai-infrastructure/models:/root/.cache/huggingface
    command: >
      --model Qwen/Qwen3.5-QwQ-32B-AWQ
      --tensor-parallel-size 1
      --gpu-memory-utilization 0.55
      --max-model-len 32768
      --enforce-eager
      --port 8000
    restart: unless-stopped
    ipc: host

  # Model Secundar: Qwen3.5-9B (Fast Responder)
  vllm-secondary:
    image: vllm/vllm-openai:latest
    container_name: vllm-qwen-9b
    runtime: nvidia
    environment:
      - HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}
    ports:
      - "8001:8000"
    volumes:
      - /data/ai-infrastructure/models:/root/.cache/huggingface
    command: >
      --model Qwen/Qwen3.5-9B-Instruct-AWQ
      --tensor-parallel-size 1
      --gpu-memory-utilization 0.25
      --max-model-len 32768
      --port 8000
    restart: unless-stopped
    ipc: host

  # Interfața utilizator (Unificarea endpoint-urilor)
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    ports:
      - "3000:8080"
    volumes:
      - /data/ai-infrastructure/webui:/app/backend/data
    environment:
      - OPENAI_API_BASE_URL=http://vllm-primary:8000/v1
      - OPENAI_API_BASE_URL_2=http://vllm-secondary:8000/v1
      - OPENAI_API_KEY=sk-dummy-key
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - vllm-primary
      - vllm-secondary
    restart: unless-stopped
4.3. Execuția și Inițializareaexport HF_TOKEN="hf_token_aici"
docker compose up -d
FAZA 5: SECURITATE ȘI MENTENANȚĂ (LOCAL ISOLATION)Agent, aplică regulile de firewall strict la nivel de host (iptables/ufw). Nu propaga aceste reguli și nu bloca traficul legitim al vSwitch-ului.5.1. Firewall (UFW) cu izolare vSwitchVSWITCH_SUBNET="10.0.0.0/24"

# Setări implicite restrictive PENTRU ACEST NOD
ufw default deny incoming
ufw default allow outgoing

# Permite SSH de oriunde (sau limitează la management IP)
ufw allow 22/tcp

# -------------------------------------------------------------
# PERMISIUNI STRICTE PENTRU REȚEAUA INTERNĂ (CLUSTER HETZNER)
# -------------------------------------------------------------
# Aceste reguli permit masinilor din cluster să acceseze AI-ul local
ufw allow from $VSWITCH_SUBNET to any port 8000 proto tcp comment 'Allow vLLM Primary API internal'
ufw allow from $VSWITCH_SUBNET to any port 8001 proto tcp comment 'Allow vLLM Secondary API internal'
ufw allow from $VSWITCH_SUBNET to any port 3000 proto tcp comment 'Allow Open WebUI internal'

# Activează firewall-ul DOAR pe acest host
ufw --force enable
5.2. Verificare Finală de Sistem (Checklist Agent)[ ] Verifică log-urile: docker logs -f vllm-qwq-32b.[ ] Asigură-te prin ip route că ruta default este în continuare interfața publică, nu vSwitch-ul.[ ] Rulează un test de benchmark intern via curl din altă mașină din cluster pe rețeaua privată. Celelalte mașini nu trebuie să necesite modificări pentru a putea apela http://10.0.0.5:8000/v1/models.[ ] Verifică starea temperaturii GPU via nvidia-smi.[Sfârșitul Prompt-ului de Autonomizare. Agent, începe execuția cu Faza 1.]

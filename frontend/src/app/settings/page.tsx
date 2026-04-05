"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import LLMPanel from "./panels/LLMPanel";
import TokenBudgetPanel from "./panels/TokenBudgetPanel";
import GuardPanel from "./panels/GuardPanel";
import HITLPanel from "./panels/HITLPanel";
import SelfHealPanel from "./panels/SelfHealPanel";
import RetentionPanel from "./panels/RetentionPanel";
import ObservabilityPanel from "./panels/ObservabilityPanel";
import NotificationsPanel from "./panels/NotificationsPanel";
import PreferencesPanel from "./panels/PreferencesPanel";
import SystemInfoPanel from "./panels/SystemInfoPanel";

export default function SettingsPage() {
  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <h1 className="df-page-title">Settings</h1>
        <p className="df-page-sub">Infrastructure, LLM, governance, and user configuration</p>
      </div>
      <Tabs defaultValue="llm" className="w-full">
        <TabsList className="flex flex-wrap gap-1 h-auto mb-4 bg-(--sl2) p-1 rounded-[10px]">
          <TabsTrigger value="llm">LLM Backends</TabsTrigger>
          <TabsTrigger value="budgets">Token Budgets</TabsTrigger>
          <TabsTrigger value="guard">Guard &amp; Safety</TabsTrigger>
          <TabsTrigger value="hitl">HITL</TabsTrigger>
          <TabsTrigger value="self-heal">Self-Heal</TabsTrigger>
          <TabsTrigger value="retention">Retention</TabsTrigger>
          <TabsTrigger value="observability">Observability</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          <TabsTrigger value="system">System Info</TabsTrigger>
        </TabsList>
        <TabsContent value="llm"><LLMPanel /></TabsContent>
        <TabsContent value="budgets"><TokenBudgetPanel /></TabsContent>
        <TabsContent value="guard"><GuardPanel /></TabsContent>
        <TabsContent value="hitl"><HITLPanel /></TabsContent>
        <TabsContent value="self-heal"><SelfHealPanel /></TabsContent>
        <TabsContent value="retention"><RetentionPanel /></TabsContent>
        <TabsContent value="observability"><ObservabilityPanel /></TabsContent>
        <TabsContent value="notifications"><NotificationsPanel /></TabsContent>
        <TabsContent value="preferences"><PreferencesPanel /></TabsContent>
        <TabsContent value="system"><SystemInfoPanel /></TabsContent>
      </Tabs>
    </div>
  );
}

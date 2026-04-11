import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Switch } from "@/components/ui/switch";

describe("Switch component", () => {
  it("renders without crash", () => {
    const { container } = render(<Switch />);
    expect(container).toBeTruthy();
  });

  it("has role='switch'", () => {
    render(<Switch />);
    expect(screen.getByRole("switch")).toBeInTheDocument();
  });

  it("is unchecked (data-state=unchecked) by default", () => {
    render(<Switch />);
    expect(screen.getByRole("switch")).toHaveAttribute("data-state", "unchecked");
  });

  it("becomes checked (data-state=checked) when clicked", () => {
    render(<Switch defaultChecked={false} />);
    const sw = screen.getByRole("switch");
    fireEvent.click(sw);
    expect(sw).toHaveAttribute("data-state", "checked");
  });

  it("starts checked when defaultChecked=true", () => {
    render(<Switch defaultChecked />);
    expect(screen.getByRole("switch")).toHaveAttribute("data-state", "checked");
  });

  it("calls onCheckedChange with the new boolean value when toggled", () => {
    const handler = vi.fn();
    render(<Switch onCheckedChange={handler} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(true);
  });

  it("calls onCheckedChange(false) when toggled off from checked state", () => {
    const handler = vi.fn();
    render(<Switch defaultChecked onCheckedChange={handler} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(handler).toHaveBeenCalledWith(false);
  });

  it("is disabled and not interactive when disabled prop is set", () => {
    const handler = vi.fn();
    render(<Switch disabled onCheckedChange={handler} />);
    const sw = screen.getByRole("switch");
    expect(sw).toBeDisabled();
    fireEvent.click(sw);
    expect(handler).not.toHaveBeenCalled();
  });

  it("merges custom className onto the root element", () => {
    render(<Switch className="my-custom-class" />);
    expect(screen.getByRole("switch")).toHaveClass("my-custom-class");
  });

  it("forwards a ref to the root DOM element", () => {
    let capturedRef: HTMLButtonElement | null = null;
    render(
      <Switch
        ref={(el) => {
          capturedRef = el;
        }}
      />
    );
    expect(capturedRef).not.toBeNull();
    expect(capturedRef).toBeInstanceOf(HTMLButtonElement);
  });

  it("is accessible via aria-label", () => {
    render(<Switch aria-label="Enable notifications" />);
    expect(screen.getByRole("switch", { name: "Enable notifications" })).toBeInTheDocument();
  });

  it("renders in a controlled manner — respects checked prop", () => {
    const { rerender } = render(<Switch checked={false} onCheckedChange={vi.fn()} />);
    expect(screen.getByRole("switch")).toHaveAttribute("data-state", "unchecked");

    rerender(<Switch checked={true} onCheckedChange={vi.fn()} />);
    expect(screen.getByRole("switch")).toHaveAttribute("data-state", "checked");
  });
});

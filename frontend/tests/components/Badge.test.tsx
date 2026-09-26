import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders text content", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders as an inline element", () => {
    const { container } = render(<Badge>Tag</Badge>);
    const badge = container.firstElementChild;
    expect(badge?.tagName.toLowerCase()).toBe("span");
  });
});

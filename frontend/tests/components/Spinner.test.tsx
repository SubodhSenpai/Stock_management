import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Spinner } from "@/components/ui/Spinner";

describe("Spinner", () => {
  it("renders an SVG with role='status'", () => {
    render(<Spinner />);
    const spinner = screen.getByRole("status", { name: "Loading" });
    expect(spinner).toBeInTheDocument();
    expect(spinner.tagName.toLowerCase()).toBe("svg");
  });

  it("defaults to size 16", () => {
    render(<Spinner />);
    const svg = screen.getByRole("status");
    expect(svg).toHaveAttribute("width", "16");
    expect(svg).toHaveAttribute("height", "16");
  });

  it("accepts a custom size", () => {
    render(<Spinner size={24} />);
    const svg = screen.getByRole("status");
    expect(svg).toHaveAttribute("width", "24");
    expect(svg).toHaveAttribute("height", "24");
  });

  // On an SVG element `className` is an SVGAnimatedString, not a string, so the class
  // list has to be read from the attribute.
  it("applies the animate-spin class", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toHaveClass("animate-spin");
  });

  it("merges a custom className", () => {
    render(<Spinner className="text-red-500" />);
    expect(screen.getByRole("status")).toHaveClass("animate-spin", "text-red-500");
  });
});

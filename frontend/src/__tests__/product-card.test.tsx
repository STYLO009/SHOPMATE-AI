import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ProductCard from "@/components/ProductCard";
import type { Product } from "@/lib/types";

const sampleProduct: Product = {
  id: "db-1",
  provider_product_id: "SMP-LAP-001",
  title: "Velocity Pro 15",
  brand: "Velocity",
  category: "laptop",
  description: "Demo laptop",
  price: 59990,
  currency: "INR",
  merchant: "SampleStore",
  product_url: "https://example.com/laptop",
  image_url: "/static/products/laptop.svg",
  specifications: { ram_gb: 16 },
  rating: 4.4,
  review_count: 128,
  availability: "in_stock",
  source_type: "sample",
  source_name: "Sample dataset (demo)",
  is_sample_data: true,
  last_verified_at: "2026-01-01T00:00:00Z",
};

describe("ProductCard", () => {
  it("renders title, price and sample-data badge", () => {
    render(<ProductCard product={sampleProduct} />);
    expect(screen.getByText("Velocity Pro 15")).toBeInTheDocument();
    expect(screen.getByText("Sample data")).toBeInTheDocument();
    expect(screen.getByText(/59,990/)).toBeInTheDocument();
    expect(screen.getByText(/4.4/)).toBeInTheDocument();
  });

  it("never presents sample listings without the badge", () => {
    render(<ProductCard product={sampleProduct} />);
    expect(screen.getByTestId("product-card")).toBeInTheDocument();
    // Sample data is badged, merchant chip shown, and no live-price claims.
    expect(screen.getByText("SampleStore")).toBeInTheDocument();
  });

  it("invokes onSave with the product", () => {
    const onSave = vi.fn();
    render(<ProductCard product={sampleProduct} onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Save product"));
    expect(onSave).toHaveBeenCalledWith(sampleProduct);
  });

  it("links out only when a real product URL exists", () => {
    const { rerender } = render(<ProductCard product={sampleProduct} />);
    const link = screen.getByRole("link", { name: /view/i });
    expect(link).toHaveAttribute("href", "https://example.com/laptop");

    rerender(<ProductCard product={{ ...sampleProduct, product_url: null }} />);
    expect(screen.queryByRole("link", { name: /view/i })).not.toBeInTheDocument();
  });
});

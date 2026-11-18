"use client";

import { motion } from "framer-motion";
import { Bookmark, ExternalLink, Star } from "lucide-react";
import { formatPrice } from "@/lib/format";
import type { Product, ProductCard as Card } from "@/lib/types";

/** Union of the two product shapes returned by the API. */
export type AnyProduct = Product | Card;

interface ProductCardProps {
  product: AnyProduct;
  onSave?: (product: AnyProduct) => void;
  onCompare?: (product: AnyProduct) => void;
  saved?: boolean;
  compareSelected?: boolean;
  actionLabel?: string;
}

export default function ProductCard({
  product,
  onSave,
  onCompare,
  saved = false,
  compareSelected = false,
  actionLabel,
}: ProductCardProps) {
  const rating = product.rating;
  const count = product.review_count ?? 0;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className="card flex flex-col gap-3 p-4"
      data-testid="product-card"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {product.is_sample_data && (
            <span className="badge-sample" title="Demo dataset — not live listings">
              Sample data
            </span>
          )}
          <span className="badge">{product.merchant}</span>
        </div>
        {onSave && (
          <button
            type="button"
            aria-label={saved ? "Remove from saved" : "Save product"}
            onClick={() => onSave(product)}
            className="rounded-lg border border-border p-1.5 transition hover:border-accent"
          >
            <Bookmark
              size={15}
              className={saved ? "fill-accent text-accent" : "text-muted"}
            />
          </button>
        )}
      </div>

      <div>
        <h3 className="font-semibold leading-snug">{product.title}</h3>
        {"brand" in product && product.brand && (
          <p className="mt-0.5 text-sm text-muted">{product.brand}</p>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-lg font-bold text-gradient">
          {formatPrice(product.price, product.currency)}
        </span>
        <div className="flex items-center gap-1 text-sm text-muted">
          <Star size={14} className="fill-warning text-warning" />
          {rating != null ? rating.toFixed(1) : "—"}
          <span className="text-xs">({count})</span>
        </div>
      </div>

      <div className="mt-auto flex items-center gap-2">
        {onCompare && (
          <button
            type="button"
            onClick={() => onCompare(product)}
            className={`btn-ghost flex-1 text-sm ${compareSelected ? "border-accent text-accent" : ""}`}
          >
            {compareSelected ? "Selected" : "Compare"}
          </button>
        )}
        {actionLabel && onSave && (
          <button type="button" onClick={() => onSave(product)} className="btn-ghost flex-1 text-sm">
            {actionLabel}
          </button>
        )}
        {product.product_url && (
          <a
            href={product.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-ghost flex items-center gap-1 text-sm"
          >
            View <ExternalLink size={13} />
          </a>
        )}
      </div>
    </motion.article>
  );
}

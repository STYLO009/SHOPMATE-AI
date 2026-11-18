/** Types mirroring the FastAPI OpenAPI schema (backend/app/schemas). */

export interface User {
  id: string;
  full_name: string;
  email: string;
  profile_image_url: string | null;
  auth_provider: string;
  email_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Product {
  id: string;
  provider_product_id: string;
  title: string;
  brand: string | null;
  category: string | null;
  description: string | null;
  price: number;
  currency: string;
  merchant: string;
  product_url: string | null;
  image_url: string | null;
  specifications: Record<string, unknown>;
  rating: number | null;
  review_count: number | null;
  availability: string;
  source_type: string;
  source_name: string;
  is_sample_data: boolean;
  last_verified_at: string | null;
}

export interface ProductCard {
  product_id: string;
  title: string;
  brand: string | null;
  merchant: string;
  price: number;
  currency: string;
  image_url: string | null;
  rating: number | null;
  review_count: number | null;
  source_type: string;
  is_sample_data: boolean;
  product_url: string | null;
}

export interface SearchResponse {
  products: Product[];
  total: number;
  query: string;
  category: string | null;
  providers_queried: string[];
  provider_errors: string[];
  is_sample_data: boolean;
  took_ms: number;
}

export interface RetailOffer {
  product_id: string;
  title: string;
  merchant: string;
  price: number;
  currency: string;
  original_price: number | null;
  discount_percentage: number | null;
  deal_title: string | null;
  category: string | null;
  description: string | null;
  availability: string;
  product_url: string | null;
  image_url: string | null;
  source_type: string;
  is_sample_data: boolean;
  last_verified_at: string;
  expires_at: string | null;
}

export interface FeaturedOffer {
  id: string;
  merchant: string;
  title: string;
  description: string | null;
  category: string | null;
  url: string;
  image_url: string | null;
  availability: string;
  source_type: string;
  is_sample_data: boolean;
  last_verified_at: string;
  start_at: string | null;
  expires_at: string | null;
}

export interface RankedProduct {
  product: ProductCard;
  final_score: number;
  factor_scores: Record<string, number>;
  reasons: string[];
}

export interface RecommendationResponse {
  ranked: RankedProduct[];
  weights: Record<string, number>;
  llm_mode: string;
  notes: string[];
}

export interface SpecDifference {
  spec: string;
  values: Record<string, string>;
  better?: string | null;
  explanation?: string | null;
}

export interface ComparisonResult {
  products: Product[];
  price_difference: number | null;
  cheapest_product_id: string | null;
  spec_differences: SpecDifference[];
  missing_specs: string[];
  stale_products: string[];
  verdict: string | null;
  best_value_id: string | null;
}

export interface ReviewTheme {
  theme: string;
  sentiment: "positive" | "negative" | "neutral";
  mentions: number;
  example_quote: string | null;
}

export interface ReviewAnalysisResponse {
  product_id: string | null;
  product_title: string | null;
  review_count: number;
  average_rating: number | null;
  positive_themes: ReviewTheme[];
  negative_themes: ReviewTheme[];
  recurring_complaints: string[];
  summary: string;
  reliability_concerns: string[];
  is_sample_data: boolean;
  llm_mode: string;
}

export interface TraceStep {
  node?: string;
  stage?: string;
  detail?: string;
  message?: string;
  [key: string]: unknown;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  reply: string;
  intent: string | null;
  products: ProductCard[];
  ranked: RankedProduct[];
  suggested_followups: string[];
  trace: TraceStep[];
  errors: string[];
  llm_mode: string;
  created_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
  context: Record<string, unknown>;
}

export interface WatchlistEntry {
  id: string;
  product: ProductCard;
  target_price: number | null;
  last_price: number | null;
  last_checked_at: string | null;
  check_count: number;
  created_at: string;
}

export interface SavedProduct {
  id: string;
  product: ProductCard;
  note: string | null;
  created_at: string;
}

export interface ApiError {
  code: string;
  message: string;
}

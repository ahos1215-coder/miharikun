export type ShipType =
  | "bulk_carrier"
  | "tanker"
  | "container"
  | "general_cargo"
  | "passenger"
  | "roro"
  | "lpg"
  | "lng"
  | "chemical"
  | "other";

export type ClassificationSociety = "NK" | "JG" | "ABS" | "DNV" | "LR" | "BV";

export type NavigationArea =
  | "international"
  | "coastal"
  | "near_sea"
  | "smooth_water";

export type Severity = "critical" | "action_required" | "informational";

export interface ShipProfile {
  id: string;
  user_id: string;
  ship_name: string;
  ship_type: ShipType;
  gross_tonnage: number;
  dwt: number | null;
  build_year: number;
  classification_society: ClassificationSociety;
  flag_state: string;
  navigation_area: NavigationArea[];
  routes: string[] | null;
  imo_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface Regulation {
  id: string;
  source: string;
  source_id: string;
  title: string;
  title_en: string | null;
  headline: string | null;
  summary_ja: string | null;
  url: string | null;
  pdf_url: string | null;
  published_at: string | null;
  effective_date: string | null;
  category: string | null;
  severity: Severity;
  confidence: number | null;
  citations: Citation[] | null;
  needs_review: boolean;
  domain: string;
  applicable_ship_types: string[] | null;
  applicable_gt_min: number | null;
  applicable_gt_max: number | null;
  created_at: string;
}

export interface Citation {
  text: string;
  page?: number;
  source?: string;
}

export interface UserMatch {
  id: string;
  regulation_id: string;
  ship_profile_id: string;
  is_applicable: boolean | null;
  match_method: string;
  confidence: number | null;
  reason: string | null;
  citations: Citation[] | null;
  notified: boolean;
  regulation?: Regulation;
}

export const SHIP_TYPE_LABELS: Record<ShipType, string> = {
  bulk_carrier: "ばら積み貨物船",
  tanker: "タンカー",
  container: "コンテナ船",
  general_cargo: "一般貨物船",
  passenger: "旅客船",
  roro: "RORO船",
  lpg: "LPG船",
  lng: "LNG船",
  chemical: "ケミカルタンカー",
  other: "その他",
};

export const CLASSIFICATION_LABELS: Record<ClassificationSociety, string> = {
  NK: "日本海事協会 (ClassNK)",
  JG: "日本政府 (JG)",
  ABS: "ABS",
  DNV: "DNV",
  LR: "Lloyd's Register",
  BV: "Bureau Veritas",
};

export const NAV_AREA_LABELS: Record<NavigationArea, string> = {
  international: "国際航海",
  coastal: "沿海",
  near_sea: "近海",
  smooth_water: "平水",
};

// --- Email-specific types (used by weekly summary email template) ---

export interface EmailRegulationItem {
  title: string;
  severity: string;
  confidence: number;
  reason: string;
  url: string;
}

export interface EmailShipSummary {
  shipName: string;
  shipType: string;
  grossTonnage: number;
  regulations: EmailRegulationItem[];
}

// --- User preferences ---

export type NotifySeverity = "all" | "critical" | "action_required";

export interface UserPreferences {
  id: string;
  user_id: string;
  email_notify: boolean;
  line_notify: boolean;
  notify_severity: NotifySeverity;
  weekly_summary: boolean;
  created_at: string;
  updated_at: string;
}

export const NOTIFY_SEVERITY_LABELS: Record<NotifySeverity, string> = {
  all: "全て",
  critical: "重要のみ",
  action_required: "緊急のみ",
};

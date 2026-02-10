export enum RatingColor {
  GREEN = 'GREEN',
  YELLOW = 'YELLOW',
  RED = 'RED',
  UNKNOWN = 'UNKNOWN'
}

// T003: Charity tier type for three-tier classification system
// - rich: Prominently featured charities with comprehensive narratives (20-25 max)
// - baseline: Standard charities searchable on browse page
// - hidden: Not publicly listed, accessible only via direct URL
export type CharityTier = 'rich' | 'baseline' | 'hidden';

export interface DimensionEvaluation {
  rating: RatingColor | string;  // Can be enum or string literal
  rationale: string;
}

// Legacy EA-style Impact Assessment (backward compatible)
export interface LegacyImpactAssessment {
  overall_rating: RatingColor | string;
  dimension_ratings: {
    problem_importance: DimensionEvaluation;
    intervention_strength: DimensionEvaluation;
    scale_of_reach: DimensionEvaluation;
    cost_effectiveness: DimensionEvaluation;
    long_term_benefit: DimensionEvaluation;
  };
  narrative: string;
  cited_sources: string[];
  key_strengths: string[];
  growth_opportunities: string[];
  confidence_level: 'high' | 'medium' | 'low';
}

// Amal Framework Types
// Valid wallet tags (based on website self-assertion model):
// - ZAKAT-ELIGIBLE: Charity explicitly claims zakat eligibility
// - SADAQAH-STRATEGIC: High-impact work, no zakat claim
// - SADAQAH-GENERAL: Standard charitable giving
// - INSUFFICIENT-DATA: Not enough info to classify
export type WalletTag = 'ZAKAT-ELIGIBLE' | 'SADAQAH-STRATEGIC' | 'SADAQAH-GENERAL' | 'INSUFFICIENT-DATA' | string;
export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'MIXED' | 'UNDERSERVED' | 'ROBUST' | 'MEASURED' | 'EMPIRICAL' | 'GROWING' | 'ANECDOTAL' | 'ORPHANED' | 'SCALABLE' | 'CROWDED' | 'CONSUMPTIVE' | 'GENERATIVE' | 'RISKY' | 'LOW-MID' | 'HIGH-GROWING' | string;
export type DirectionalImpactStatus = 'SAFE' | 'HARMFUL' | 'NEUTRAL';

export interface AmalDimensionScore {
  score: number;
  level?: ConfidenceLevel;
  rationale?: string;  // Legacy field
  narrative?: string;  // New field - replaces rationale in some data
  evidence?: string[];
  max?: number;  // Maximum possible score (from v3.4.2 data)
  rating_label?: string;  // Human-readable label (from v3.4.2 data)
  confidence?: string | { score: number; rationale: string };  // Confidence assessment
  sub_scores?: Record<string, unknown>;  // Sub-dimension scores (flexible schema)
}

export interface AmalTier1StrategicFit {
  subtotal: number;
  systemic_leverage: AmalDimensionScore;
  ummah_gap: AmalDimensionScore;
}

export interface AmalTier2Execution {
  subtotal: number;
  // New field names (v2 rubric)
  operational_capability?: AmalDimensionScore;
  mission_delivery?: AmalDimensionScore;
  // Legacy field names (backwards compatibility)
  absorptive_capacity?: AmalDimensionScore;
  evidence_of_impact?: AmalDimensionScore;
}

// Consolidated zakat guidance (replaces wallet_routing + zakatClaim)
export interface AmalZakatGuidance {
  charityClaimsZakat: boolean;
  claimEvidence: string | null;
  asnafCategories: string[];
  rationale: string;
  donorAdvisory: string | null;
  scholarlyNote: string | null;
}

// Legacy wallet routing (deprecated - use zakatGuidance instead)
export interface AmalWalletRouting {
  tag: WalletTag;
  matching_categories: string[];
  rationale: string;
  advisory: string | null;
  donor_guidance?: string;
  donor_growth_message?: string;
  disclaimer: string | null;
}

export interface AmalSummary {
  headline: string;
  strengths: string[];
  improvement_areas: string[];
  donor_guidance: string | null;
  narrative: string;
}

export interface AmalDataConfidence {
  level: ConfidenceLevel;
  score?: number;
  gaps?: string[];
  data_gaps?: string[];
  sources_used?: string[];
}

// Evidence-Based Giving Types (EBG)
// Based on GiveWell's evidence hierarchy and charity evaluation standards

export type EvidenceGrade = 'A' | 'B' | 'C' | 'D' | 'E' | 'F';

export interface EvidenceQualityGrade {
  grade: EvidenceGrade;
  methodologyType?: string | null;  // e.g., "RCT/meta-analysis", "Quasi-experimental"
  sources: string[];
  rationale: string;
}

export type VerificationTier = 'tier_1_gold' | 'tier_2_strong' | 'tier_3_moderate';

export interface ThirdPartyVerification {
  verified: boolean;
  sources: string[];
  verificationType?: string | null;  // e.g., "independent_evaluation", "accreditation"
  tier?: VerificationTier | null;
}

export type BenchmarkComparison = 'above_benchmark' | 'at_benchmark' | 'below_benchmark' | 'insufficient_data';

export interface CostEffectivenessBenchmark {
  causeArea: string;
  costPerBeneficiary?: number | null;
  benchmarkName: string;
  benchmarkRange?: [number, number | null] | null;
  comparison: BenchmarkComparison;
  ratio?: number | null;
  dataSource?: string | null;
}

// Extended GiveWell data (beyond basic top charity status)
export type RoomForFunding = 'limited' | 'significant' | 'available';

export interface GiveWellExtendedData {
  // Basic (already in EBG)
  isTopCharity: boolean;
  evidenceRating: EvidenceGrade;
  // Cost-effectiveness
  costPerLifeSaved?: number | null;
  costPerIntervention?: number | null;  // $/net, $/vaccine, etc.
  cashBenchmarkMultiplier?: number | null;  // X times as effective as cash
  costPerLifeRange?: [number, number] | null;  // [low, high] range
  // Spending allocation
  programSpendingPct?: number | null;
  overheadPct?: number | null;
  // Scale and reach
  countriesServed?: string[];
  countriesCount?: number | null;
  totalBeneficiaries?: number | null;
  // Organizational
  staffSize?: number | null;
  annualBudget?: number | null;
  // Monitoring data
  usageRate?: number | null;  // Post-distribution usage %
  usageRateSelfReported?: number | null;
  usageRateInferred?: number | null;
  // Funding
  roomForFunding?: RoomForFunding | null;
  fundingGap?: number | null;
}

// Extended BBB Wise Giving Alliance data
export type AuditStatus = 'audited' | 'reviewed' | 'compiled' | 'internal';

export interface BBBExtendedData {
  // Basic (already in EBG)
  meetsStandards: boolean | null;
  standardsMet: number;
  standardsNotMet: number;
  // Category status
  governancePass: boolean | null;
  effectivenessPass: boolean | null;
  financesPass: boolean | null;
  solicitationsPass: boolean | null;
  // Governance details (Standards 1-5)
  boardSize?: number | null;
  boardSizeMeetsStandard?: boolean | null;
  boardMeetingsPerYear?: number | null;
  boardMeetingsMeetsStandard?: boolean | null;
  compensatedBoardMembers?: number | null;
  boardCompensationMeetsStandard?: boolean | null;
  conflictOfInterestPolicy?: boolean | null;
  // Financial metrics (Standards 8-14)
  programExpenseRatio?: number | null;  // 0-1 (min 0.65)
  programExpenseMeetsStandard?: boolean | null;
  fundraisingExpenseRatio?: number | null;  // 0-1 (max 0.35)
  fundraisingExpenseMeetsStandard?: boolean | null;
  reservesRatio?: number | null;  // Max 3x annual expenses
  reservesMeetsStandard?: boolean | null;
  auditStatus?: AuditStatus | null;
  hasRequiredAudit?: boolean | null;
  // Effectiveness (Standards 6-7)
  effectivenessPolicy?: boolean | null;
  hasEffectivenessAssessment?: boolean | null;
  // Transparency (Standards 15-20)
  annualReportAvailable?: boolean | null;
  donorPrivacyPolicy?: boolean | null;
  form990OnWebsite?: boolean | null;
  complaintResponsePolicy?: boolean | null;
  // Metadata
  lastReviewDate?: string | null;
  reviewUrl?: string | null;
}

// Legacy zakat claim (deprecated - use zakatGuidance instead)
export interface AmalZakatClaim {
  charityClaimsZakat: boolean;
  claimEvidence: string | null;
  asnafCategory: string | null;
  notes: string | null;
}

// Plain English explanations for each dimension (standalone, no scores needed)
export interface DimensionExplanations {
  [key: string]: unknown;
  credibility?: string;   // Verification, transparency, and evidence quality
  impact?: string;        // Program effectiveness, cost efficiency, and financial health
  alignment?: string;     // Muslim donor fit and cause urgency
  // Legacy fields (backward compat with old cached narratives)
  trust?: string;
  evidence?: string;
  effectiveness?: string;
  fit?: string;
}

// New baseline narrative structure from pipeline
export interface BaselineNarrative {
  summary: string;
  headline: string;
  strengths: string[];
  amal_score_rationale: string;
  areas_for_improvement: string[];
  dimension_explanations?: DimensionExplanations;  // Human-readable dimension analysis
  all_citations?: RichCitation[];  // Citations (if available in baseline)
}

// Ideal donor profile - describes WHO should donate, not what charity does
export interface IdealDonorProfile {
  best_for_summary: string;           // "Best for donors who..." (1-2 sentences)
  donor_motivations: string[];        // Why donors choose this charity
  giving_considerations: string[];    // Key factors to consider
  not_ideal_for?: string | null;      // Honest note about who might prefer alternatives
  citation_ids?: string[];
}

// Citation for rich narratives
export interface RichCitation {
  id: string;                         // "[1]", "[2]", etc.
  claim: string;                      // The specific claim cited
  source_name: string;                // "Form 990 (2023)", "Charity Navigator"
  source_url?: string | null;
  source_type?: string;               // form990, rating, website, etc.
  confidence?: number;                // 0-1
}

// Rich narrative structure with citations (premium content)
export interface RichNarrative {
  summary: string;                    // 500-800 words with citations
  headline: string;
  strengths: Array<{
    point: string;
    detail: string;
    citation_ids: string[];
  }>;
  areas_for_improvement: Array<{
    area: string;
    context: string;
    citation_ids: string[];
  }>;
  amal_score_rationale: string;
  dimension_explanations?: {
    credibility?: { explanation: string; improvement?: string; citation_ids: string[] };
    impact?: { explanation: string; improvement?: string; citation_ids: string[] };
    alignment?: { explanation: string; improvement?: string; citation_ids: string[] };
    // Legacy fields (backward compat with cached rich narratives)
    trust?: { explanation: string; improvement?: string; citation_ids: string[] };
    evidence?: { explanation: string; improvement?: string; citation_ids: string[] };
    effectiveness?: { explanation: string; improvement?: string; citation_ids: string[] };
    fit?: { explanation: string; improvement?: string; citation_ids: string[] };
  };
  case_against?: {
    summary: string;
    risk_factors: string[];
    mitigation_notes?: string | null;
    citation_ids: string[];
  };
  peer_comparison?: {
    peer_group: string;
    differentiator: string;
    similar_orgs: string[];
    citation_ids: string[];
  };
  ideal_donor_profile?: IdealDonorProfile;  // Donor-centric "Best For"
  all_citations?: RichCitation[];
  data_confidence?: {
    form_990_tax_year?: number | null;
    confidence_score?: number;
    total_citations?: number;
    unique_sources?: number;
    known_gaps?: string[];
    ratings_last_updated?: string;
    website_last_crawled?: string;
  };
  confidence?: {
    level?: string;
    data_freshness?: string;
    sources_used?: string[];
    score?: number;
    notes?: string;
    data_gaps?: string[];
  };
  // Impact Evidence Deep Dive
  impact_evidence?: {
    evidence_grade: string;
    evidence_grade_explanation?: string;
    theory_of_change?: string;
    theory_of_change_summary?: string;
    rct_available?: boolean;
    external_evaluations?: string[];
    why_evidence_matters?: string;
    outcome_tracking_years?: number;
    citation_ids?: string[];
  };
  // Long-Term Outlook
  long_term_outlook?: {
    founded_year?: number;
    years_operating?: number;
    maturity_stage?: string;
    revenue_growth_3yr?: number;
    room_for_funding?: string;
    room_for_funding_explanation?: string;
    strategic_priorities?: string[];
    citation_ids?: string[];
  };
  // Financial Deep Dive
  financial_deep_dive?: {
    annual_revenue?: number;
    yearly_financials?: Array<{
      year: number;
      revenue?: number;
      expenses?: number;
      net_assets?: number;
    }>;
    revenue_cagr_3yr?: number;
    reserves_months?: number;
    program_expense_ratio?: number;
    admin_ratio?: number;
    fundraising_ratio?: number;
    cn_financial_score?: number;
    industry_program_ratio?: number;
    peer_program_ratio_median?: number;
    peer_count?: number;
    citation_ids?: string[];
  };
  // Organizational Capacity / Leadership
  organizational_capacity?: {
    ceo_name?: string;
    ceo_compensation?: number;
    ceo_compensation_pct_revenue?: number;
    board_size?: number;
    independent_board_pct?: number;
    employees_count?: number;
    volunteers_count?: number;
    programs_count?: number;
    geographic_reach?: string;
    has_conflict_policy?: boolean;
    has_financial_audit?: boolean;
    staff_per_million_revenue?: number;
    payroll_to_revenue_pct?: number;
    citation_ids?: string[];
  };
  // Donor Fit Matrix
  donor_fit_matrix?: {
    cause_area?: string;
    giving_style?: string;
    evidence_rigor?: string;
    zakat_status?: string;
    zakat_asnaf_served?: string[];
    geographic_focus?: string[];
    tax_deductible?: boolean;
    citation_ids?: string[];
    giving_tiers?: Array<{ amount?: string; range?: string; label?: string; impact?: string }>;
  };
  // Similar Organizations with differentiators
  similar_organizations?: Array<{
    name: string;
    differentiator?: string;
  }>;
  // Grantmaking Profile (for charities that make grants)
  grantmaking_profile?: {
    is_significant_grantmaker?: boolean;
    total_grants?: number;
    domestic_grants?: number;
    foreign_grants?: number;
    grant_count?: number;
    top_recipients?: string[];
    regions_served?: string[];
    grant_strategy?: string;
    citation_ids?: string[];
  };
  // BBB Wise Giving Alliance Assessment
  bbb_assessment?: {
    meets_all_standards?: boolean;
    standards_met?: number;
    standards_not_met?: string[];
    governance_status?: string;
    effectiveness_status?: string;
    finances_status?: string;
    audit_type?: string;
    summary?: string;
    review_url?: string;
    citation_ids?: string[];
  };
  // Extended analysis paragraphs
  strengths_deep_dive?: string[];
  // Citation statistics
  citation_stats?: {
    total_count: number;
    unique_sources: number;
    high_confidence_count: number;
    by_source_type?: Record<string, number>;
  };
  // Zakat guidance
  zakat_guidance?: {
    eligibility?: string;
    classification?: string | null;
  };
  // Amal scores (some rich narratives embed these)
  amal_scores?: {
    amal_score?: number;
    wallet_tag?: string;
    impact_tier?: string;
    confidence_tier?: string;
    confidence_scores?: {
      trust?: number;
      evidence?: number;
      effectiveness?: number;
      fit?: number;
    };
  };
  // Legacy field names (for backward compatibility)
  key_strengths?: string[];
}

// Dimension scores (2-dimension framework)
export interface ConfidenceScores {
  impact?: number;        // out of 50
  alignment?: number;     // out of 50
  dataConfidence?: number; // 0.0-1.0 (outside score)
  // Legacy fields (backward compat with old cached data)
  credibility?: number;   // old 3-dimension format
  trust?: number;
  evidence?: number;
  effectiveness?: number;
  fit?: number;
}

// Score component — atomic scoring unit within a dimension
export interface ScoreComponentDetail {
  name: string;
  scored: number;
  possible: number;
  evidence: string;
  status: 'full' | 'partial' | 'missing';
  improvement_suggestion?: string | null;
  improvement_value: number;
}

// 2-dimension detail interfaces
// (credibility is now internal — its components feed Impact and DataConfidence)
export interface CredibilityDetails {
  score: number;
  components: ScoreComponentDetail[];
  rationale: string;
  verification_tier: string;
  theory_of_change_level: string;
  evidence_quality_level: string;
  confidence_notes: string[];
  corroboration_notes?: string[];
  capacity_limited_evidence?: boolean;
}

export interface ImpactDetails {
  score: number;
  components: ScoreComponentDetail[];
  rationale: string;
  cost_per_beneficiary: number | null;
  directness_level: string;
  impact_design_categories: string[];
  rubric_archetype?: string;
}

export interface AlignmentDetails {
  score: number;
  components: ScoreComponentDetail[];
  rationale: string;
  muslim_donor_fit_level: string;
  cause_urgency_label: string;
}

// Legacy detail interfaces (for backward compat with old cached evaluations)
export interface TrustDetails {
  score: number;
  verification_tier: string;
  verification_tier_points: number;
  data_quality: string;
  data_quality_points: number;
  transparency: string;
  transparency_points: number;
  rationale: string;
  confidence_notes: string[];
  corroboration_notes?: string[];
  improvement_suggestions?: string[];
}

export interface EvidenceDetails {
  score: number;
  evidence_grade: string;
  evidence_grade_points: number;
  evidence_grade_rationale: string;
  outcome_measurement: string;
  outcome_measurement_points: number;
  theory_of_change: string;
  theory_of_change_points: number;
  rationale: string;
  third_party_evaluated: boolean;
  rct_available: boolean;
  improvement_suggestions?: string[];
  capacity_limited_evidence?: boolean;
}

export interface EffectivenessDetails {
  score: number;
  cost_efficiency: string;
  cost_efficiency_points: number;
  cost_per_beneficiary: number | null;
  cause_benchmark: string | null;
  scale_efficiency: string;
  scale_efficiency_points: number;
  room_for_funding: string;
  room_for_funding_points: number;
  rationale: string;
  cash_comparison: string | null;
  improvement_suggestions?: string[];
}

export interface FitDetails {
  score: number;
  counterfactual: string;
  counterfactual_points: number;
  counterfactual_rationale: string;
  cause_importance: string;
  cause_importance_points: number;
  cause_neglectedness: string;
  cause_neglectedness_points: number;
  rationale: string;
  improvement_suggestions?: string[];
}

export interface RiskFactor {
  category: string;
  description: string;
  severity: string;
  data_source?: string;
  mitigation?: string;
}

export interface RiskDetails {
  risks: RiskFactor[];
  overall_risk_level: string;
  risk_summary: string;
  total_deduction: number;
}

export interface ZakatDetails {
  bonus_points: number;
  charity_claims_zakat: boolean;
  claim_evidence: string | null;
  asnaf_category: string | null;
}

export interface DataConfidenceDetails {
  overall: number;       // 0.0-1.0
  badge: string;         // HIGH, MEDIUM, LOW
  verification_tier?: string;
  transparency_label?: string;
  data_quality_label?: string;
}

export interface ScoreDetails {
  // 2-dimension framework (credibility feeds Impact + DataConfidence)
  credibility?: CredibilityDetails;
  impact?: ImpactDetails;
  alignment?: AlignmentDetails;
  data_confidence?: DataConfidenceDetails;
  // Legacy 4-dimension fields (backward compat)
  trust?: TrustDetails;
  evidence?: EvidenceDetails;
  effectiveness?: EffectivenessDetails;
  fit?: FitDetails;
  // Shared
  risks: RiskDetails;
  zakat?: ZakatDetails;
  risk_deduction: number;
  score_summary?: string;
}

export interface AmalEvaluation {
  charity_ein: string;
  charity_name: string;
  amal_score: number;
  wallet_tag: WalletTag;
  baseline_narrative?: BaselineNarrative;
  rich_narrative?: RichNarrative;  // Premium content with citations
  confidence_scores?: ConfidenceScores;
  score_details?: ScoreDetails;  // Full scorer output with all rationales
  evaluation_date: string;
  // Extended Amal evaluation fields
  methodology_version?: string;
  tier_1_strategic_fit?: AmalTier1StrategicFit;
  tier_2_execution?: AmalTier2Execution;
  wallet_routing?: AmalWalletRouting;
  summary?: AmalSummary;
  data_confidence?: AmalDataConfidence;
  zakat_classification?: string | null;
  impact_tier?: string;
  confidence_tier?: string;
  // Direct pillar scores (alternative format used by some data)
  trust?: AmalDimensionScore;
  evidence?: AmalDimensionScore;
  effectiveness?: AmalDimensionScore;
  fit?: AmalDimensionScore;
}

// Union type for backward compatibility - can be either legacy or Amal
export type ImpactAssessment = LegacyImpactAssessment;

export interface ConfidenceAssessment {
  confidence_tier: 'HIGH' | 'MODERATE' | 'LOW' | 'INSUFFICIENT_DATA';
  dimension_ratings: {
    transparency: RatingColor | string;  // Can be enum or string literal
    governance: RatingColor | string;
    financial_controls: RatingColor | string;
    third_party_verification: RatingColor | string;
    reporting_quality: RatingColor | string;
  };
  narrative: string; // Generated by AI
}

// Nested financials structure (preferred)
export interface CharityFinancials {
  totalRevenue?: number | null;
  totalExpenses?: number | null;
  programExpenses?: number | null;
  adminExpenses?: number | null;
  fundraisingExpenses?: number | null;
  programExpenseRatio?: number | null;
  fiscalYear?: number | null;
  // Balance sheet data
  totalAssets?: number | null;
  totalLiabilities?: number | null;
  netAssets?: number | null;
  // Working capital months (balance sheet derived)
  workingCapitalMonths?: number | null;
}

// Website evidence signals (transparency indicators from charity website)
export interface WebsiteEvidenceSignals {
  claims_longitudinal?: boolean | null;
  claims_rcts?: boolean | null;
  claims_third_party_eval?: boolean | null;
  disclosure_richness?: number | null;
  reports_annual_report?: boolean | null;
  reports_board_info?: boolean | null;
  reports_methodology?: boolean | null;
  reports_outcome_metrics?: boolean | null;
}

// Evidence quality signals for scoring transparency
export interface EvidenceQuality {
  hasOutcomeMethodology?: boolean | null;
  hasMultiYearMetrics?: boolean | null;
  thirdPartyEvaluated?: boolean | null;
  evaluationSources?: string[] | null;
  receivesFoundationGrants?: boolean | null;
}

// Baseline governance data (for charities without rich narratives)
export interface BaselineGovernance {
  boardSize?: number | null;
  independentBoardMembers?: number | null;
  ceoCompensation?: number | null;
}

// Program with description (website2 format)
export interface ProgramDetail {
  name: string;
  description: string;
}

// Raw input data for the AI to evaluate
export interface CharityRawData {
  name: string;
  description: string;
  mission: string;
  ein?: string;
  website?: string;
  donationUrl?: string; // Direct donation page URL
  city?: string | null; // City location
  state?: string | null; // State location
  programs?: string[] | ProgramDetail[]; // Supports both flat list and detailed format
  populationsServed?: string[]; // T051 - Target populations/beneficiaries
  geographicCoverage?: string[]; // T052 - Countries/regions served
  program_expense_ratio: number; // 0-1 (ratio) or 0-100 (percentage)
  admin_fundraising_ratio: number; // 0-100
  beneficiaries_annual: number;
  geographic_reach: string[]; // e.g., ["Turkey", "Syria"] (deprecated, use geographicCoverage)
  board_members_count: number;
  independent_board_members: number;
  audit_performed: boolean;
  zakat_policy: string; // Description of Zakat handling
  transparency_level: string; // e.g., "Gold", "Platinum", "None"
  red_flags: string[]; // List of potential issues
  outcomes_evidence: string; // Text description of outcomes
  fiscal_year?: number; // T036 - Fiscal year for financial data (deprecated, use financials.fiscalYear)
  total_revenue?: number; // T037 - Total revenue (deprecated, use financials.totalRevenue)
  admin_expenses?: number; // T038 - Administrative expenses (deprecated)
  fundraising_expenses?: number; // T039 - Fundraising expenses (deprecated)
  financials?: CharityFinancials; // Preferred nested structure
}

export interface CharityScores {
  overall: number | null;
  financial: number | null;
  accountability: number | null;
  transparency: number | null;
  effectiveness: number | null;
}

// Awards and recognition from external sources
export interface CharityAwards {
  cnBeacons?: string[] | null;  // e.g., ["Encompass Award", "4-Star Rating"]
  cnUrl?: string | null;  // Link to Charity Navigator profile
  candidSeal?: string | null;  // e.g., "Platinum" (only Platinum highlighted)
  candidUrl?: string | null;  // Link to Candid profile
  bbbStatus?: string | null;  // e.g., "Meets Standards"
  bbbReviewUrl?: string | null;  // Link to BBB evaluation (always shown for transparency)
}

// T065 - US4: Source Attribution
export interface SourceAttributionField {
  source?: string; // Single source for selected fields
  sources?: string[]; // Multiple sources for merged fields
  source_url?: string; // URL for the source
  value?: string | number | null; // The attributed value
  method: 'selection' | 'priority' | 'merged';
}

export interface SourceAttributionData {
  [fieldName: string]: SourceAttributionField;
}

// =============================================================================
// Multi-Lens Scoring Types (Strategic Believer + Traditional Zakat)
// =============================================================================

// Strategic Believer Evaluation
export interface StrategicResilienceAssessment {
  score: number;              // max 30
  loop_breaking_raw: number;  // 0-10
  loop_breaking_points: number;
  rationale: string;
}

export interface StrategicLeverageAssessment {
  score: number;              // max 25
  multiplier_raw: number;     // 0-10
  multiplier_points: number;
  rationale: string;
}

export interface StrategicFutureProofingAssessment {
  score: number;                // max 25
  asset_creation_raw: number;   // 0-10
  asset_creation_points: number;
  sovereignty_raw: number;      // 0-10
  sovereignty_points: number;
  rationale: string;
}

export interface StrategicCompetenceAssessment {
  score: number;                       // max 20
  trust_contribution: number;          // 0-8
  toc_contribution: number;            // 0-5  (theory of change)
  outcome_contribution: number;        // 0-4  (outcome measurement rigor)
  evidence_grade_contribution: number; // 0-3  (tiebreaker)
  rationale: string;
}

// Rich strength/area types for strategic narrative (with detail and citations)
export interface RichStrengthItem {
  point: string;
  detail: string;
  citation_ids: string[];
}

export interface RichAreaItem {
  area: string;
  context: string;
  citation_ids: string[];
}

// Strategic Believer narrative (same base shape as BaselineNarrative plus rich fields)
export interface StrategicNarrative {
  summary: string;
  headline: string;
  strengths: Array<string | RichStrengthItem>;
  amal_score_rationale?: string;
  areas_for_improvement: Array<string | RichAreaItem>;
  dimension_explanations?: DimensionExplanations;
  all_citations?: RichCitation[];
  score_rationale?: string;
  score_interpretation?: string;
  ideal_donor_profile?: IdealDonorProfile;
  case_against?: {
    summary: string;
    risk_factors: string[];
    mitigation_notes?: string | null;
    citation_ids?: string[];
  };
}

export interface RichStrategicNarrative extends StrategicNarrative {
  strategic_deep_dive?: {
    loop_breaking_evidence: string;
    multiplier_analysis: string;
    asset_durability: string;
    sovereignty_assessment: string;
  };
  operational_capacity?: {
    institutional_maturity: string;
    financial_sustainability: string;
    execution_track_record: string;
  };
  peer_comparison?: {
    archetype_context: string;
    strategic_score_context: string;
  };
  dimension_scores?: Record<string, unknown>;
}

export interface StrategicBelieverEvaluation {
  total_score: number;
  archetype: string;  // RESILIENCE, LEVERAGE, SOVEREIGNTY, ASSET_CREATION, DIRECT_SERVICE
  archetype_label?: string;  // Human-readable label (e.g., "Institution Builder")
  archetype_description?: string;  // 1-2 sentence explanation
  dimensions: {
    resilience: StrategicResilienceAssessment;
    leverage: StrategicLeverageAssessment;
    future_proofing: StrategicFutureProofingAssessment;
    competence: StrategicCompetenceAssessment;
  };
  narrative?: StrategicNarrative | BaselineNarrative | null;
  rich_narrative?: RichStrategicNarrative | null;
}

// Traditional Zakat Evaluation
export interface ZakatFiqhComplianceAssessment {
  score: number;              // max 35
  wallet_tag_points: number;  // ZAKAT-ELIGIBLE=20, SADAQAH-ELIGIBLE=5
  asnaf_clarity_points: number;
  wallet_tag: string;
  asnaf_category?: string | null;
  rationale: string;
}

export interface ZakatDirectnessAssessment {
  score: number;                      // max 25
  program_ratio_points: number;       // 0-15
  beneficiary_proximity_points: number; // 0-10
  program_expense_ratio?: number | null;
  rationale: string;
}

export interface ZakatCommunityIdentityAssessment {
  score: number;                  // max 25
  muslim_fit_points: number;      // high=20, medium=12, low=5
  islamic_identity_bonus: number; // 0-5
  muslim_charity_fit?: string | null;
  rationale: string;
}

export interface ZakatSpeedOfDeliveryAssessment {
  score: number;                // max 20
  cause_speed_points: number;   // 0-18
  urgency_bonus: number;  // 0-2, acute need in conflict zones
  cause_area?: string | null;
  rationale: string;
}

// Zakat narrative (same rich fields as StrategicNarrative, minus archetype)
export interface ZakatNarrative {
  summary: string;
  headline: string;
  strengths: Array<string | RichStrengthItem>;
  areas_for_improvement: Array<string | RichAreaItem>;
  score_rationale?: string;
  dimension_explanations?: Record<string, string>;
  all_citations?: RichCitation[];
  score_interpretation?: string;
  ideal_donor_profile?: IdealDonorProfile;
  case_against?: { summary: string; risk_factors: string[]; mitigation_notes?: string | null; };
}

export interface TraditionalZakatEvaluation {
  total_score: number;
  dimensions: {
    fiqh_compliance: ZakatFiqhComplianceAssessment;
    directness: ZakatDirectnessAssessment;
    community_identity: ZakatCommunityIdentityAssessment;
    speed_of_delivery: ZakatSpeedOfDeliveryAssessment;
  };
  narrative?: ZakatNarrative | BaselineNarrative | null;
  metadata?: {
    asnaf_categories_served?: string[];
    zakat_policy_url?: string | null;
    direct_page_verified?: boolean;
    islamic_identity_signals?: Record<string, boolean | string[]>;
  };
}

export interface CharityProfile {
  id?: string; // Optional - may be derived from ein
  name: string;
  tier?: CharityTier; // T003 - Charity tier (rich | baseline | hidden)
  category: string; // e.g., "Emergency Relief", "Education"
  ein?: string;
  website?: string | null;
  donationUrl?: string | null; // Direct donation page URL
  city?: string | null; // City location
  state?: string | null; // State location
  location?: {
    address?: string | null;
    city?: string | null;
    state?: string | null;
    zip?: string | null;
  } | null;
  programs?: string[]; // T050 - Programs offered
  populationsServed?: string[]; // T051 - Target populations/beneficiaries
  geographicCoverage?: string[]; // T052 - Countries/regions served
  scores?: CharityScores; // T053-T055 - Charity Navigator ratings (optional for legacy data)
  awards?: CharityAwards; // CN beacons, Candid seals, other recognition
  sourceAttribution?: SourceAttributionData; // T058 - Source attribution metadata
  financials?: CharityFinancials; // Top-level financials (preferred)
  websiteEvidenceSignals?: WebsiteEvidenceSignals | null; // Transparency indicators from website
  baselineGovernance?: BaselineGovernance | null; // Governance for baseline charities (no rich narrative)
  rawData: CharityRawData;
  impactAssessment?: ImpactAssessment; // Optional for pipeline-generated charities
  confidenceAssessment?: ConfidenceAssessment; // Optional for pipeline-generated charities
  amalEvaluation?: AmalEvaluation; // Amal Impact Matrix evaluation
  // Strategic/Zakat lens evaluations removed from frontend (pipeline preserves them)
  scoreSummary?: string | null; // Plain-English score explanation
  hideFromCurated?: boolean; // Hide from default browse view (still searchable/filterable)
  // Evaluation track for alternative scoring rubrics
  evaluationTrack?: 'STANDARD' | 'NEW_ORG' | 'RESEARCH_POLICY' | null;
  foundedYear?: number | null;
  // Form 990 filing status (for religious orgs exempt from filing)
  form990Exempt?: boolean | null;
  form990ExemptReason?: string | null;
  noFilings?: boolean | null;
  // Category and cause metadata
  primaryCategory?: string | null; // MECE primary category
  causeArea?: string | null; // Raw cause area from rich_narrative
  causeTags?: string[] | null; // Cause tags for filtering/display
  programFocusTags?: string[] | null; // Program focus tags for similarity matching (e.g., "arts-culture-media")
  // Impact highlight for landing page featured charities
  impactHighlight?: string | null;
  // Extended fields for card display
  impactTier?: string | null; // Impact tier rating
  categoryMetadata?: { neglectedness?: string | null } | null;
  headline?: string | null; // Short headline from narrative
  totalRevenue?: number | null; // Annual revenue
  // New pipeline fields surfaced for donor value
  beneficiariesServedAnnually?: number | null; // Self-reported
  zakatClaimEvidence?: string[] | null; // Corroborated evidence
  archetype?: string | null; // Strategic archetype (e.g., RESILIENCE, LEVERAGE)
  evidenceQuality?: EvidenceQuality | null; // Evidence quality signals
  asnafServed?: string[] | null; // Zakat asnaf categories served
  // Trust signals from pipeline synthesis
  trustSignals?: {
    hasAnnualReport?: boolean | null;
    hasAuditedFinancials?: boolean | null;
    candidSeal?: string | null;
    isConflictZone?: boolean | null;
    nonprofitSizeTier?: string | null;
    employeesCount?: number | null;
    volunteersCount?: number | null;
  } | null;
  // Theory of change (from website/PDFs)
  theoryOfChange?: string | null;
  // Grants data (from Form 990 Schedule I/F)
  grantsData?: Array<{ name?: string; recipient?: string; amount?: number }> | null;
  // Targeting data
  targeting?: {
    populationsServed?: string[] | null;
    geographicCoverage?: string[] | null;
  } | null;
}

// ============================================================================
// User Feature Types (Issue 1: Foundation)
// ============================================================================

// Giving priority categories that users can allocate percentages to
export type GivingPriorityCategory =
  | 'education'
  | 'poverty'
  | 'healthcare'
  | 'humanitarian'
  | 'dawah'
  | 'environment'
  | 'research'
  | 'other';

// Geographic regions for preference filtering
export type GeographicPreference =
  | 'domestic'
  | 'south-asia'
  | 'middle-east'
  | 'africa'
  | 'southeast-asia'
  | 'global';

// Fiqh preferences for zakat calculations
export interface FiqhPreferences {
  madhab?: 'hanafi' | 'shafi' | 'maliki' | 'hanbali' | null;
  zakatOnJewelry?: boolean;
  zakatOnBusinessAssets?: boolean;
  zakatOnStocks?: 'market_value' | 'dividend_only' | null;
  zakatOnRental?: boolean;
}

// Giving priorities as percentages (should sum to 100) - LEGACY
export type GivingPriorities = Partial<Record<GivingPriorityCategory, number>>;

// ============================================================================
// Giving Buckets - User-defined allocation categories
// ============================================================================

// Tag types for flexible categorization
export type TagType = 'cause' | 'geography' | 'custom';

export interface GivingTag {
  id: string;        // e.g., "pakistan", "education", "local-community"
  label: string;     // e.g., "Pakistan", "Education", "Local Community"
  type: TagType;
}

// User-defined giving bucket (allocation category)
export interface GivingBucket {
  id: string;                // UUID
  name: string;              // e.g., "Pakistan Relief", "Local Education"
  tags: string[];            // Tag IDs that match this bucket
  percentage: number;        // Allocation percentage (0-100)
  color?: string;            // Optional color for UI
  description?: string;      // Optional description
}

// Explicit charity-to-bucket assignment (overrides auto-matching)
export interface CharityBucketAssignment {
  charityEin: string;
  bucketId: string;
}

// User profile stored in Supabase
export interface UserProfile {
  id: string; // UUID, FK to auth.users
  givingPriorities: GivingPriorities; // LEGACY - use givingBuckets instead
  geographicPreferences: GeographicPreference[];
  fiqhPreferences: FiqhPreferences;
  zakatAnniversary: string | null; // ISO date string
  targetZakatAmount: number | null; // Annual zakat target
  // New flexible allocation system
  givingBuckets: GivingBucket[];
  charityBucketAssignments: CharityBucketAssignment[];
  createdAt: string;
  updatedAt: string;
}

// Bookmark entry
export interface Bookmark {
  id: string;
  userId: string;
  charityEin: string;
  notes: string | null;
  createdAt: string;
}

// Asset categories for zakat calculation
export interface ZakatAssets {
  cash?: number;
  gold?: number;
  silver?: number;
  stocks?: number;
  businessInventory?: number;
  receivables?: number;
  rentalIncome?: number;
  other?: number;
}

// Liability categories
export interface ZakatLiabilities {
  debts?: number;
  loans?: number;
  creditCards?: number;
  other?: number;
}

// Zakat calculation record
export interface ZakatCalculation {
  id: string;
  userId: string;
  year: number;
  assets: ZakatAssets;
  liabilities: ZakatLiabilities;
  nisabValue: number | null;
  zakatDue: number | null;
  calculatedAt: string;
}

// Giving history entry
export interface GivingHistoryEntry {
  id: string;
  userId: string;
  charityEin: string | null; // null for untracked charities
  charityName: string;
  amount: number;
  date: string; // ISO date
  category: 'zakat' | 'sadaqah' | 'other';
  zakatYear: number | null; // e.g., 2025 (only for zakat donations)
  paymentSource: string | null; // text with autocomplete from history
  receiptReceived: boolean;
  taxDeductible: boolean;
  matchEligible: boolean;
  matchStatus: 'submitted' | 'received' | null;
  matchAmount: number | null;
  notes: string | null;
  createdAt: string;
}

// Charity target for per-charity dollar goals
export interface CharityTarget {
  id: string;
  userId: string;
  charityEin: string;
  targetAmount: number;
  createdAt: string;
  updatedAt: string;
}

// Portfolio allocation
export interface PortfolioAllocation {
  id: string;
  userId: string;
  charityEin: string;
  allocationPercent: number;
  createdAt: string;
  updatedAt: string;
}

// Comparison state (client-side only, not stored in DB)
export interface CompareState {
  selectedCharities: string[]; // EINs, max 3
}

// Summary type for charity cards in bookmarks/compare views
export interface CharitySummary {
  id: string;
  ein: string;
  name: string;
  tier: CharityTier;
  amalScore: number;
  walletTag: string;
  impactTier: string | null;
  evaluationTrack?: string | null;
  pillarScores?: {
    credibility: number;
    impact: number;
    alignment: number;
  };
  causeTags?: string[] | null;
  programFocusTags?: string[] | null;
  headline?: string | null;
  scoreSummary?: string | null;
  asnafServed?: string[] | null;
}

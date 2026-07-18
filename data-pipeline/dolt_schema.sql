-- dolt_schema.sql — GENERATED FILE. Do not hand-edit.
-- Regenerate: uv run python migrations/regenerate_dolt_schema.py
-- Verify:     uv run python migrations/regenerate_dolt_schema.py --check
-- Source: live SHOW CREATE statements from the zakaat Dolt database, plus
-- any tables listed in FALLBACK_DDL that don't exist live yet.

CREATE TABLE `agent_discoveries` (
  `id` char(36) NOT NULL,
  `charity_ein` varchar(12) NOT NULL,
  `agent_type` varchar(50) NOT NULL,
  `discovery_method` varchar(30) NOT NULL,
  `source_name` varchar(100) NOT NULL,
  `source_url` varchar(1024),
  `search_query` text,
  `raw_html` longtext,
  `parsed_data` json,
  `grounding_metadata` json,
  `confidence` decimal(3,2) DEFAULT '1.00',
  `relevance_score` decimal(3,2),
  `discovered_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `raw_content` longtext,
  `updated_at` timestamp,
  PRIMARY KEY (`id`),
  KEY `idx_discovery_agent` (`agent_type`),
  KEY `idx_discovery_charity` (`charity_ein`),
  KEY `idx_discovery_method` (`discovery_method`),
  UNIQUE KEY `uq_discovery` (`charity_ein`,`agent_type`,`source_url`(255)),
  CONSTRAINT `fk_discovery_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `charities` (
  `ein` varchar(12) NOT NULL,
  `name` varchar(255) NOT NULL,
  `mission` text,
  `website` varchar(512),
  `category` varchar(100),
  `address` text,
  `city` varchar(100),
  `state` varchar(50),
  `zip` varchar(20),
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ein`),
  KEY `idx_charities_category` (`category`),
  KEY `idx_charities_state` (`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `charity_data` (
  `charity_ein` varchar(12) NOT NULL,
  `has_islamic_identity` tinyint(1),
  `serves_muslim_populations` tinyint(1),
  `muslim_charity_fit` varchar(20),
  `total_revenue` bigint,
  `program_expenses` bigint,
  `admin_expenses` bigint,
  `fundraising_expenses` bigint,
  `program_expense_ratio` decimal(5,4),
  `charity_navigator_score` decimal(5,2),
  `transparency_score` decimal(5,2),
  `nonprofit_size_tier` varchar(30),
  `detected_cause_area` varchar(100),
  `claims_zakat_eligible` tinyint(1),
  `beneficiaries_served_annually` int,
  `has_annual_report` tinyint(1),
  `has_audited_financials` tinyint(1),
  `candid_seal` varchar(50),
  `source_attribution` json,
  `cause_tags` json,
  `program_focus_tags` json,
  `ntee_code` varchar(10),
  `cause_detection_source` varchar(30),
  `is_conflict_zone` tinyint(1),
  `working_capital_months` decimal(10,2),
  `primary_category` varchar(100),
  `category_importance` varchar(10),
  `category_neglectedness` varchar(10),
  `evaluation_track` varchar(30),
  `founded_year` int,
  `policy_influence` json,
  `synthesized_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `charity_navigator_rating` varchar(20),
  `is_muslim_charity` tinyint(1),
  `total_assets` bigint,
  `total_liabilities` bigint,
  `net_assets` bigint,
  `board_size` int,
  `independent_board_members` int,
  `ceo_compensation` bigint,
  `form_990_exempt` tinyint(1),
  `form_990_exempt_reason` varchar(255),
  `populations_served` json,
  `geographic_coverage` json,
  `website_evidence_signals` json,
  `strategic_classification` json DEFAULT NULL,
  `zakat_metadata` json,
  `strategic_evidence` json,
  `theory_of_change` text,
  `grants_made` json,
  `metrics_json` json,
  `total_expenses` bigint,
  `cn_overall_score` decimal(5,2),
  `cn_financial_score` decimal(5,2),
  `cn_accountability_score` decimal(5,2),
  `employees_count` int,
  `volunteers_count` int,
  `has_theory_of_change` tinyint(1),
  `reports_outcomes` tinyint(1),
  `has_outcome_methodology` tinyint(1),
  `has_multi_year_metrics` tinyint(1),
  `third_party_evaluated` tinyint(1),
  `evaluation_sources` json,
  `receives_foundation_grants` tinyint(1),
  `candid_metrics_count` int,
  `candid_max_years_tracked` int,
  `no_filings` tinyint(1),
  `zakat_claim_evidence` text,
  `slug` varchar(100),
  PRIMARY KEY (`charity_ein`),
  CONSTRAINT `fk_charitydata_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `citations` (
  `id` char(36) NOT NULL,
  `charity_ein` varchar(12) NOT NULL,
  `narrative_type` varchar(30) NOT NULL,
  `claim` text NOT NULL,
  `source_name` varchar(200) NOT NULL,
  `source_type` varchar(50) NOT NULL,
  `source_url` varchar(1024),
  `quote` text,
  `confidence` decimal(3,2) DEFAULT '1.00',
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `access_date` timestamp,
  PRIMARY KEY (`id`),
  KEY `idx_citation_charity` (`charity_ein`),
  KEY `idx_citation_narrative` (`charity_ein`,`narrative_type`),
  CONSTRAINT `fk_citation_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `evaluations` (
  `charity_ein` varchar(12) NOT NULL,
  `amal_score` int,
  `wallet_tag` varchar(50),
  `confidence_tier` varchar(20),
  `impact_tier` varchar(20),
  `zakat_classification` varchar(30),
  `confidence_scores` json,
  `score_details` json,
  `impact_scores` json,
  `baseline_narrative` json,
  `rich_narrative` json,
  `judge_score` int,
  `information_density` decimal(5,4),
  `state` varchar(20) DEFAULT 'pending',
  `evaluated_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `llm_cost_usd` decimal(10,4),
  `strategic_score` int DEFAULT NULL,
  `zakat_score` int DEFAULT NULL,
  `score_profiles` json DEFAULT NULL,
  `strategic_narrative` json DEFAULT NULL,
  `zakat_narrative` json DEFAULT NULL,
  `rich_strategic_narrative` json,
  `rubric_version` varchar(12) DEFAULT NULL,
  `judge_content_hash` varchar(16),
  PRIMARY KEY (`charity_ein`),
  KEY `idx_evaluations_state` (`state`),
  KEY `idx_evaluations_wallet_tag` (`wallet_tag`),
  CONSTRAINT `fk_evaluations_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

-- export_exclusions: defined in ExportExclusionRepository.ensure_table (src/db/repository.py) — created lazily on first write, so it may not exist in the live DB yet; DDL below is hardcoded from that canonical source and is superseded by the live SHOW CREATE TABLE once it exists
CREATE TABLE `export_exclusions` (
  `charity_ein` varchar(12) NOT NULL,
  `judge_score` int,
  `reason` text,
  `excluded_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`charity_ein`,`excluded_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `judge_verdicts` (
  `id` char(36) NOT NULL,
  `charity_ein` varchar(12) NOT NULL,
  `commit_hash` varchar(40) NOT NULL,
  `judge_name` varchar(50) NOT NULL,
  `passed` tinyint(1) NOT NULL,
  `error_count` int DEFAULT '0',
  `warning_count` int DEFAULT '0',
  `issues` json,
  `cost_usd` decimal(10,6) DEFAULT '0.000000',
  `validated_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_verdict_charity` (`charity_ein`),
  KEY `idx_verdict_commit` (`commit_hash`),
  KEY `idx_verdict_passed` (`passed`),
  UNIQUE KEY `uq_verdict` (`charity_ein`,`commit_hash`,`judge_name`),
  CONSTRAINT `fk_verdict_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

-- organization_families: created ad-hoc 2026-01..02 — holds real data, no code writers yet
CREATE TABLE `organization_families` (
  `id` int NOT NULL AUTO_INCREMENT,
  `family_id` varchar(50) NOT NULL COMMENT 'Shared identifier for related orgs (e.g., mpac, icna)',
  `charity_ein` varchar(20) NOT NULL COMMENT 'EIN of the charity',
  `role` varchar(20) DEFAULT 'member' COMMENT 'primary, member, chapter, subsidiary',
  `entity_type` varchar(20) COMMENT '501c3, 501c4, chapter, fiscal_sponsor',
  `notes` text COMMENT 'Additional context about the relationship',
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ein` (`charity_ein`),
  KEY `idx_family` (`family_id`),
  UNIQUE KEY `unique_family_ein` (`family_id`,`charity_ein`),
  CONSTRAINT `organization_families_ibfk_1` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin COMMENT='Groups related organizations (c3/c4 pairs, chapters, subsidiaries)';

CREATE TABLE `pdf_documents` (
  `id` char(36) NOT NULL,
  `charity_ein` varchar(12) NOT NULL,
  `document_type` varchar(50),
  `fiscal_year` int,
  `url` varchar(1024),
  `storage_path` varchar(512),
  `extracted_data` json,
  `status` varchar(20) DEFAULT 'pending',
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pdf_charity_ein` (`charity_ein`),
  KEY `idx_pdf_type_year` (`document_type`,`fiscal_year`),
  CONSTRAINT `fk_pdf_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `phase_cache` (
  `charity_ein` varchar(12) NOT NULL,
  `phase` varchar(20) NOT NULL,
  `code_fingerprint` varchar(64) NOT NULL,
  `ran_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `cost_usd` decimal(10,6) DEFAULT '0.000000',
  PRIMARY KEY (`charity_ein`,`phase`),
  KEY `idx_phase_cache_phase` (`phase`),
  KEY `idx_phase_cache_ran_at` (`ran_at`),
  CONSTRAINT `fk_phase_cache_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE TABLE `raw_scraped_data` (
  `id` char(36) NOT NULL,
  `charity_ein` varchar(12) NOT NULL,
  `source` varchar(50) NOT NULL,
  `raw_content` longtext,
  `parsed_json` json,
  `scraped_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `success` tinyint(1) DEFAULT '1',
  `error_message` text,
  `retry_count` int DEFAULT '0',
  `last_failure_reason` text,
  PRIMARY KEY (`id`),
  KEY `idx_raw_charity_ein` (`charity_ein`),
  KEY `idx_raw_source` (`source`),
  KEY `idx_raw_success` (`success`),
  UNIQUE KEY `uq_raw_charity_source` (`charity_ein`,`source`),
  CONSTRAINT `fk_raw_charity` FOREIGN KEY (`charity_ein`) REFERENCES `charities` (`ein`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE VIEW `charity_list` AS SELECT
  c.ein,
  c.name,
  c.category,
  c.mission,
  c.website,
  cd.program_expense_ratio,
  cd.charity_navigator_score,
  e.amal_score,
  e.wallet_tag,
  e.confidence_tier,
  e.zakat_classification,
  e.baseline_narrative
FROM charities c
LEFT JOIN charity_data cd ON cd.charity_ein = c.ein
LEFT JOIN evaluations e ON e.charity_ein = c.ein
WHERE e.state = 'approved';

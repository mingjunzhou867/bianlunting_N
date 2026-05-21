-- Migration: Add hardship_category_code and hardship_policy_match to hardship_certification
-- These columns were referenced by policy pack YAML but missing from the DDL.
-- Run: mysql -u root -p zhicetong_t2s < scripts/migrate_add_hardship_columns.sql

ALTER TABLE `hardship_certification`
  ADD COLUMN `hardship_category_code` varchar(50) DEFAULT NULL COMMENT '困难类别编码(如ED_001)' AFTER `hardship_category`,
  ADD COLUMN `hardship_policy_match` varchar(10) DEFAULT NULL COMMENT '政策匹配标记(1=匹配/0=不匹配)' AFTER `hardship_category_code`;

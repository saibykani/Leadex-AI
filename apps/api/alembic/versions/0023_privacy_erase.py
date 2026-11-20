"""privacy: erasure of append-only rows for a data subject

Revision ID: 0023
Revises: 0022

privacy_erase_lead(lead) deletes the lead's call transcripts and clears the payloads of its call events and lead
activities. These tables are append-only for the application role; this SECURITY DEFINER function is the only
exception, it acts solely inside the caller's bound organization (app.current_org) and returns the row count.
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None
ROLE = "leadex_app"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
CREATE OR REPLACE FUNCTION privacy_erase_lead(p_lead uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_org uuid := NULLIF(current_setting('app.current_org', true), '')::uuid;
  n integer := 0;
  k integer;
BEGIN
  IF v_org IS NULL THEN
    RAISE EXCEPTION 'privacy_erase_lead: no organization bound';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM leads WHERE id = p_lead AND organization_id = v_org) THEN
    RAISE EXCEPTION 'privacy_erase_lead: lead not in current organization';
  END IF;
  DELETE FROM call_transcripts WHERE organization_id = v_org
    AND call_id IN (SELECT id FROM call_sessions WHERE organization_id = v_org AND lead_id = p_lead);
  GET DIAGNOSTICS k = ROW_COUNT; n := n + k;
  UPDATE call_events SET data = NULL WHERE organization_id = v_org
    AND call_id IN (SELECT id FROM call_sessions WHERE organization_id = v_org AND lead_id = p_lead);
  GET DIAGNOSTICS k = ROW_COUNT; n := n + k;
  UPDATE lead_activities SET data = NULL WHERE organization_id = v_org AND lead_id = p_lead;
  GET DIAGNOSTICS k = ROW_COUNT; n := n + k;
  RETURN n;
END $$""")
    op.execute("REVOKE ALL ON FUNCTION privacy_erase_lead(uuid) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION privacy_erase_lead(uuid) TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS privacy_erase_lead(uuid)")

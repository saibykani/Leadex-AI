"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { agentsApi, type Agent } from "@/lib/agents";
import { Alert } from "@/components/ui";
import { AgentBuilder } from "../_builder";
import { LearningPanel } from "../_learning";

export default function AgentPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { agentsApi.get(id).then(setAgent).catch((e) => setError(e.message)); }, [id]);
  if (error) return <Alert>{error}</Alert>;
  if (!agent) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-6">
      <AgentBuilder key={agent.id} agent={agent} />
      <LearningPanel agentId={agent.id} />
    </div>
  );
}

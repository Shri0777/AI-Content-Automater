"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink, Empty, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { WEEKDAYS } from "@/lib/format";
import type { Plan, ScheduleRule } from "@/lib/types";

function describeRule(rule: ScheduleRule): string {
  const days = rule.days_of_week.length === 7 ? "Every day" : rule.days_of_week.map((day) => WEEKDAYS[day]).join(", ");
  return `${days} at ${rule.times.join(", ")}`;
}

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.plans().then(setPlans).catch(setError);
  }, []);

  return (
    <>
      <PageHeader
        title="Plans"
        intro="A plan says what to post about, where, and when."
        action={<ButtonLink href="/app/plans/new">New plan</ButtonLink>}
      />
      <div className="mt-8">
        <ErrorNote error={error} />
        {!plans && !error && <Loading />}
        {plans?.length === 0 && (
          <Empty title="No plans yet">
            <p>Create one to choose topics, the accounts to post to, and your posting times.</p>
          </Empty>
        )}
        {plans && plans.length > 0 && (
          <ul className="border-t border-ink/30">
            {plans.map((plan) => (
              <li key={plan.id}>
                <Link href={`/app/plans/${plan.id}`} className="flex flex-col gap-2 border-b border-ink/10 py-5 hover:bg-mist/40 md:flex-row md:items-start md:justify-between">
                  <span>
                    <span className="text-title text-ink">{plan.name}</span>
                    <span className="mt-1 block">{plan.topics.map((topic) => topic.name).join(", ")}</span>
                  </span>
                  <span className="text-sm md:text-right">
                    {plan.paused ? <span className="text-caution">Paused</span> : plan.approval_mode === "auto" ? "Posts on its own when clean" : "Asks you first"}
                    {plan.schedule_rules.map((rule) => (
                      <span key={rule.id} className="block">{describeRule(rule)}</span>
                    ))}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

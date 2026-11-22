"use client";

/*
 * Edit a plan's posting times: some weekdays, at some local times, in one
 * timezone. A plan can have several rules (for example weekdays at 09:00,
 * weekends at 11:00).
 */

import { useMemo } from "react";

import { WEEKDAYS } from "@/lib/format";
import type { ScheduleRule } from "@/lib/types";

function allTimezones(): string[] {
  return typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC"];
}

function RuleEditor({ rule, onChange, onRemove, index }: { rule: ScheduleRule; onChange: (rule: ScheduleRule) => void; onRemove: () => void; index: number }) {
  const zones = useMemo(() => allTimezones(), []);

  function toggleDay(day: number) {
    const days = rule.days_of_week.includes(day)
      ? rule.days_of_week.filter((d) => d !== day)
      : [...rule.days_of_week, day].sort();
    onChange({ ...rule, days_of_week: days });
  }

  function setTime(position: number, value: string) {
    const times = [...rule.times];
    times[position] = value;
    onChange({ ...rule, times });
  }

  return (
    <fieldset className="border border-ink/20 p-4">
      <legend className="px-1 text-ink">Posting times {index + 1}</legend>
      <div role="group" aria-label="Days" className="flex flex-wrap gap-1">
        {WEEKDAYS.map((name, day) => (
          <button
            key={name}
            type="button"
            aria-pressed={rule.days_of_week.includes(day)}
            onClick={() => toggleDay(day)}
            className={`min-h-11 min-w-12 border px-2 ${rule.days_of_week.includes(day) ? "border-ink bg-ink text-paper" : "border-ink/25 text-ink"}`}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        {rule.times.map((time, position) => (
          <label key={position} className="flex flex-col gap-1 text-sm">
            Time {position + 1}
            <input
              type="time"
              value={time}
              required
              onChange={(event) => setTime(position, event.target.value)}
              className="min-h-11 border border-ink/25 px-2 text-ink"
            />
          </label>
        ))}
        <button type="button" className="min-h-11 px-2 text-signal underline-offset-4 hover:underline" onClick={() => onChange({ ...rule, times: [...rule.times, "18:00"] })}>
          Add a time
        </button>
        {rule.times.length > 1 && (
          <button type="button" className="min-h-11 px-2 underline-offset-4 hover:underline" onClick={() => onChange({ ...rule, times: rule.times.slice(0, -1) })}>
            Remove last time
          </button>
        )}
      </div>
      <label className="mt-4 flex flex-col gap-1 text-sm">
        Timezone
        <select
          value={rule.timezone}
          onChange={(event) => onChange({ ...rule, timezone: event.target.value })}
          className="min-h-11 w-full min-w-0 max-w-sm border border-ink/25 px-2 text-ink"
        >
          {zones.map((zone) => (
            <option key={zone}>{zone}</option>
          ))}
        </select>
      </label>
      <button type="button" onClick={onRemove} className="mt-4 min-h-11 text-danger underline-offset-4 hover:underline">
        Remove these times
      </button>
    </fieldset>
  );
}

export function ScheduleEditor({ rules, onChange, defaultTimezone }: { rules: ScheduleRule[]; onChange: (rules: ScheduleRule[]) => void; defaultTimezone: string }) {
  function update(index: number, rule: ScheduleRule) {
    onChange(rules.map((current, position) => (position === index ? rule : current)));
  }
  return (
    <div className="flex flex-col gap-4">
      {rules.map((rule, index) => (
        <RuleEditor key={index} index={index} rule={rule} onChange={(changed) => update(index, changed)} onRemove={() => onChange(rules.filter((_, position) => position !== index))} />
      ))}
      <button
        type="button"
        className="min-h-11 self-start border border-ink/30 px-4 text-ink hover:border-ink"
        onClick={() => onChange([...rules, { days_of_week: [0, 1, 2, 3, 4], times: ["09:00"], timezone: defaultTimezone }])}
      >
        Add posting times
      </button>
      {rules.length === 0 && <p className="text-sm">No posting times: posts are only made when you choose “Make a post now”.</p>}
    </div>
  );
}

/** Rules as the API wants them: no empty times or days. */
export function cleanRules(rules: ScheduleRule[]): ScheduleRule[] {
  return rules
    .map((rule) => ({ days_of_week: rule.days_of_week, times: rule.times.filter(Boolean), timezone: rule.timezone }))
    .filter((rule) => rule.days_of_week.length > 0 && rule.times.length > 0);
}

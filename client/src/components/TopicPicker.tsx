"use client";

/*
 * Choose a plan's topics: search the built-in catalogue (grouped by
 * category) and pick several, or add your own topic with its own search
 * words and instructions for the AI. Keyboard: type to filter, arrow keys to
 * move, Enter to pick or unpick, Escape to close the list.
 */

import { useId, useMemo, useState } from "react";

import { Button } from "@/components/ui";
import type { Topic, TopicCatalogue, TopicChoice } from "@/lib/types";

const MAX_TOPICS = 6;

function matches(choice: TopicChoice, query: string): boolean {
  const text = `${choice.label} ${choice.description} ${choice.category}`.toLowerCase();
  return query.toLowerCase().split(/\s+/).every((word) => text.includes(word));
}

function Chips({ topics, onRemove }: { topics: Topic[]; onRemove: (index: number) => void }) {
  if (topics.length === 0) return <p className="text-sm">No topics yet. Pick at least one.</p>;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Chosen topics">
      {topics.map((topic, index) => (
        <li key={`${topic.preset}-${topic.name}`} className="flex items-center gap-1 bg-ink py-1 pr-1 pl-3 text-paper">
          <span>{topic.name}{topic.preset === "custom" && <span className="text-paper/70"> (yours)</span>}</span>
          <button type="button" onClick={() => onRemove(index)} aria-label={`Remove ${topic.name}`} className="flex size-9 items-center justify-center hover:bg-paper/15">
            ×
          </button>
        </li>
      ))}
    </ul>
  );
}

function CustomTopicForm({ onAdd, onCancel }: { onAdd: (topic: Topic) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [words, setWords] = useState("");
  const [instructions, setInstructions] = useState("");
  const ready = name.trim() !== "" && words.split(",").some((word) => word.trim() !== "");
  const field = "border-b border-body/50 py-2 text-ink outline-none focus:border-signal";
  return (
    <div className="flex flex-col gap-4 border border-ink/20 p-4">
      <label className="flex flex-col gap-1.5 text-sm">
        Topic name
        <input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder="Indian EV market" className={`${field} text-base`} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        Words to look for in the news (separate with commas)
        <input value={words} onChange={(event) => setWords(event.target.value)} maxLength={300} placeholder="electric vehicle, EV, battery, India" className={`${field} text-base`} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        Your instructions for the AI (optional)
        <textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} maxLength={1000} rows={3} placeholder="Focus on prices in rupees and what changes for buyers." className="border border-body/40 p-3 text-base text-ink outline-none focus:border-signal" />
      </label>
      <p className="text-sm">It reads Hacker News and major tech news sites for these words.</p>
      <div className="flex gap-2">
        <Button type="button" disabled={!ready} onClick={() => onAdd({ name: name.trim(), preset: "custom", search_words: words, instructions })}>
          Add topic
        </Button>
        <Button type="button" variant="quiet" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

export function TopicPicker({ catalogue, topics, onChange }: { catalogue: TopicCatalogue; topics: Topic[]; onChange: (topics: Topic[]) => void }) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [adding, setAdding] = useState(false);
  const found = useMemo(() => catalogue.topics.filter((choice) => matches(choice, query)), [catalogue, query]);
  const chosen = (key: string) => topics.some((topic) => topic.preset === key);
  const full = topics.length >= MAX_TOPICS;

  function toggle(choice: TopicChoice) {
    if (chosen(choice.key)) onChange(topics.filter((topic) => topic.preset !== choice.key));
    else if (!full) onChange([...topics, { name: choice.label, preset: choice.key }]);
  }

  function handleKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + found.length) % Math.max(found.length, 1));
    } else if (event.key === "Enter" && open && found[active]) {
      event.preventDefault();
      toggle(found[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Chips topics={topics} onRemove={(index) => onChange(topics.filter((_, position) => position !== index))} />
      <div className="relative">
        <label htmlFor={`${listId}-search`} className="text-sm">Find a topic ({catalogue.topics.length} to choose from, up to {MAX_TOPICS} per plan)</label>
        <input
          id={`${listId}-search`}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && found[active] ? `${listId}-${found[active].key}` : undefined}
          value={query}
          autoComplete="off"
          placeholder="Search: security, Python, startups, space…"
          onChange={(event) => { setQuery(event.target.value); setActive(0); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={handleKey}
          className="mt-1.5 w-full border border-ink/30 px-3 py-2.5 text-ink outline-none focus:border-signal"
        />
        {open && (
          <ul id={listId} role="listbox" aria-multiselectable="true" aria-label="Topics" className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto border border-ink/30 bg-paper shadow-lg">
            {found.length === 0 && <li className="p-3 text-sm">No topic matches. Add your own below.</li>}
            {catalogue.categories.map((category) => {
              const inCategory = found.filter((choice) => choice.category === category);
              if (inCategory.length === 0) return null;
              return (
                <li key={category} role="presentation">
                  <p className="bg-mist px-3 py-1.5 text-sm text-ink">{category}</p>
                  <ul role="group" aria-label={category}>
                    {inCategory.map((choice) => {
                      const isActive = found[active]?.key === choice.key;
                      return (
                        <li
                          key={choice.key}
                          id={`${listId}-${choice.key}`}
                          role="option"
                          aria-selected={chosen(choice.key)}
                          onMouseDown={(event) => { event.preventDefault(); toggle(choice); }}
                          className={`flex cursor-pointer gap-3 px-3 py-2 ${isActive ? "bg-signal/10" : ""}`}
                        >
                          <span aria-hidden="true" className={`mt-1 size-4 shrink-0 border ${chosen(choice.key) ? "border-ink bg-ink" : "border-ink/40"}`} />
                          <span>
                            <span className="block text-ink">{choice.label}</span>
                            <span className="block text-sm">{choice.description}</span>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {full && <p className="text-sm text-caution">A plan can follow up to {MAX_TOPICS} topics.</p>}
      {adding ? (
        <CustomTopicForm onAdd={(topic) => { onChange([...topics, topic]); setAdding(false); }} onCancel={() => setAdding(false)} />
      ) : (
        <Button type="button" variant="secondary" className="self-start" disabled={full} onClick={() => setAdding(true)}>
          Add your own topic
        </Button>
      )}
    </div>
  );
}

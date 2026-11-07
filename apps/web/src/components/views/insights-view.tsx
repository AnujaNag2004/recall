"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import Link from "next/link";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useWorkspaces } from "@/components/app/app-context";
import { EmptyState, ErrorState, PageBody, PageHeader } from "@/components/app/page-states";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, type Insight, type Metrics } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { ScoreRing } from "./home-view";

type Category = { category: string; saved: number; acted: number };
type TrendPoint = { week_ending: string; ratio: number; acted: number; total: number };
type Changed = { task_id: string; title: string; save_id: string | null; save_title: string | null };

function Categories({ items }: { items: Category[] }) {
  const most = Math.max(...items.map((item) => item.saved), 1);
  return (
    <div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.category}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="capitalize">{item.category}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {item.acted} of {item.saved} acted on
              </span>
            </div>
            {/* The track's length is how much you saved; the fill is how much you did. */}
            <div
              className="mt-1.5 h-2 rounded-full bg-muted"
              style={{ width: `${(item.saved / most) * 100}%` }}
            >
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(item.acted / Math.max(item.saved, 1)) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-muted ring-1 ring-border" aria-hidden />
          Saved
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-primary" aria-hidden />
          Acted on
        </span>
      </div>
    </div>
  );
}

function Trend({ points }: { points: TrendPoint[] }) {
  const data = points.map((p) => ({ ...p, percent: Math.round(p.ratio * 100), label: formatDate(p.week_ending) }));
  return (
    <>
      <div className="h-56" role="img" aria-label="Save-to-Action score by week. The table below lists the values.">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            <YAxis domain={[0, 100]} unit="%" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--popover-foreground)",
              }}
              formatter={(value) => [`${value}%`, "Score"]}
            />
            <Line
              type="monotone"
              dataKey="percent"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--primary)", strokeWidth: 0 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-xs text-muted-foreground">
        <summary className="cursor-pointer">Show as a table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <thead>
            <tr>
              <th className="py-1 font-medium">Week ending</th>
              <th className="font-medium">Score</th>
              <th className="font-medium">Acted on</th>
            </tr>
          </thead>
          <tbody>
            {data.map((point) => (
              <tr key={point.week_ending}>
                <td className="py-0.5">{point.label}</td>
                <td>{point.percent}%</td>
                <td>
                  {point.acted} of {point.total}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  );
}

function InsightCard({ insight }: { insight: Insight }) {
  const content = insight.content as {
    headline?: string;
    sections?: { topic: string; summary: string; action: string }[];
    insights?: string[];
    challenge?: string | null;
  };
  if (insight.kind === "reflection") {
    return (
      <li className="rounded-xl border bg-card p-4 shadow-sm">
        <p className="text-xs text-muted-foreground">Reflection, week of {formatDate(insight.period_start)}</p>
        <ul className="mt-2 space-y-1.5 text-sm">
          {content.insights?.map((line) => <li key={line}>{line}</li>)}
        </ul>
        {content.challenge && (
          <p className="mt-3 rounded-lg bg-primary/5 p-3 text-sm">
            <span className="font-medium text-primary">A challenge, if you like: </span>
            {content.challenge}
          </p>
        )}
      </li>
    );
  }
  return (
    <li className="rounded-xl border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground">Digest, week of {formatDate(insight.period_start)}</p>
      <p className="mt-1 font-medium">{content.headline}</p>
      <ul className="mt-2 space-y-2 text-sm">
        {content.sections?.map((section) => (
          <li key={section.topic}>
            <span className="font-medium">{section.topic}: </span>
            <span className="text-muted-foreground">{section.summary}</span>
            <p className="text-xs text-primary">{section.action}</p>
          </li>
        ))}
      </ul>
    </li>
  );
}

export function InsightsView() {
  const { active } = useWorkspaces();
  const metrics = useQuery({
    queryKey: ["metrics", active?.id],
    queryFn: () => apiFetch<Metrics>(`/workspaces/${active?.id}/metrics/save-to-action`),
    enabled: Boolean(active),
  });
  const insights = useQuery({
    queryKey: ["insights", active?.id],
    queryFn: () => apiFetch<Insight[]>(`/workspaces/${active?.id}/insights`),
    enabled: Boolean(active),
  });

  const data = metrics.data;
  const categories = (data?.categories ?? []) as unknown as Category[];
  const changed = (data?.changed ?? []) as unknown as Changed[];

  return (
    <PageBody>
      <PageHeader title="Insights" lead="What your saves actually led to." />
      <div className="mt-6">
        {metrics.isPending ? (
          <Skeleton className="h-64 rounded-xl" />
        ) : metrics.isError ? (
          <ErrorState message={metrics.error.message} onRetry={() => void metrics.refetch()} />
        ) : !data || data.score.total === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="No score yet"
            body="Your score starts once a save finishes processing."
          />
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <section className="rounded-xl border bg-card p-5 shadow-sm">
              <h2 className="text-sm font-medium">Save-to-Action score</h2>
              <div className="mt-4 flex items-center gap-5">
                <ScoreRing ratio={data.score.ratio} label={`${data.score.acted} of ${data.score.total}`} />
                <p className="text-sm text-muted-foreground">
                  {data.streak_days > 0
                    ? `You're on a ${data.streak_days} day streak.`
                    : "Finish one small step to start a streak."}
                </p>
              </div>
            </section>
            <section className="rounded-xl border bg-card p-5 shadow-sm">
              <h2 className="text-sm font-medium">What you save, and what you do</h2>
              <div className="mt-4">
                <Categories items={categories} />
              </div>
            </section>
            <section className="rounded-xl border bg-card p-5 shadow-sm md:col-span-2">
              <h2 className="text-sm font-medium">Over time</h2>
              <div className="mt-4">
                <Trend points={data.trend as unknown as TrendPoint[]} />
              </div>
            </section>
            {changed.length > 0 && (
              <section className="rounded-xl border bg-card p-5 shadow-sm md:col-span-2">
                <h2 className="text-sm font-medium">Things your saves changed</h2>
                <ul className="mt-3 space-y-2 text-sm">
                  {changed.map((item) => (
                    <li key={item.task_id}>
                      <span className="font-medium">{item.title}</span>
                      {item.save_id && item.save_title && (
                        <span className="text-muted-foreground">
                          {" "}
                          from{" "}
                          <Link href={`/saves/${item.save_id}`} className="hover:underline">
                            {item.save_title}
                          </Link>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>

      {(insights.data?.length ?? 0) > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-medium">Weekly notes</h2>
          <ul className="mt-3 space-y-3">
            {insights.data?.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </ul>
        </section>
      )}
    </PageBody>
  );
}

"""Fills the demo account with realistic, invented data. Safe to re-run: it resets first.

Needs DATABASE_URL and DEMO_EMAIL, and that user must already exist in Supabase Auth
(the signup trigger gives them a personal workspace). Everyone and everything here is
invented. Saves are stored as processed, so this needs no AI keys.
"""

import asyncio
import json
import os
import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.db.session import service_session

random.seed(7)
NOW = datetime.now(UTC)
HISTORY_DAYS = 28


def S(title, source, mode, intent, topics, summary, points, tasks, done=0):  # noqa: N802
    return dict(
        title=title, source=source, mode=mode, intent=intent, topics=topics,
        summary=summary, points=points, tasks=tasks, done=done,
    )  # fmt: skip


STUDENT = [
    S("Graph algorithms in 15 minutes", "youtube", "study", "learn", ["Algorithms"],
      "A fast tour of BFS, DFS and Dijkstra, and how to spot a graph inside an interview problem.",
      ["BFS finds shortest paths when edges cost the same.", "DFS suits cycle detection.",
       "Dijkstra handles non-negative weights."],
      ["Solve 1 graph problem", "Step through BFS on a visualizer"], 2),
    S("Dynamic programming lecture notes", "pdf", "study", "learn", ["Algorithms"],
      "Lecture notes on overlapping subproblems, memoization and tabulation, with knapsack.",
      ["Memoization caches recursive results.", "Tabulation fills a table bottom up."],
      ["Do the knapsack exercise"], 1),
    S("Operating systems: process scheduling", "pdf", "study", "learn", ["Operating Systems"],
      "Compares round robin, priority and multilevel feedback queue scheduling.",
      ["Round robin is fair but can be slow.", "Priority scheduling risks starvation."],
      ["Write a one-page comparison"], 1),
    S("Virtual memory explained", "youtube", "study", "learn", ["Operating Systems"],
      "How paging and translation lookaside buffers make memory look larger than it is.",
      ["Pages map virtual to physical addresses.", "A TLB caches recent translations."],
      ["Review the paging diagram"], 0),
    S("SQL joins with examples", "article", "study", "reference", ["Databases"],
      "Inner, left and full joins explained with small example tables.",
      ["Left joins keep every row on the left.", "Join on indexed columns for speed."],
      ["Practice three join queries"], 1),
    S("Database indexing basics", "article", "study", "learn", ["Databases"],
      "How B-tree indexes speed up reads, and what they cost on writes.",
      ["Indexes trade write speed for read speed."], ["Add an index in the practice project"], 0),
    S("How to revise for finals", "article", "study", "try", ["Study Habits"],
      "Spaced repetition and active recall beat rereading for long-term memory.",
      ["Test yourself rather than rereading.", "Space out sessions."],
      ["Plan this week's revision"], 1),
    S("The Pomodoro technique", "article", "study", "try", ["Study Habits"],
      "Work in focused 25 minute blocks with short breaks to keep attention fresh.",
      ["Short breaks protect focus."], ["Try two pomodoros tonight"], 1),
    S("Linear algebra: eigenvalues intuition", "youtube", "study", "learn", ["Mathematics"],
      "A visual explanation of what eigenvalues and eigenvectors mean geometrically.",
      ["Eigenvectors keep their direction under a transformation."], ["Work through one 2x2 example"], 0),
    S("Probability cheat sheet", "pdf", "study", "reference", ["Mathematics"],
      "A summary of conditional probability, Bayes' rule and common distributions.",
      ["Bayes' rule updates beliefs with evidence."], ["Memorize Bayes' rule"], 0),
    S("Networking: TCP vs UDP", "article", "study", "learn", ["Networking"],
      "TCP guarantees delivery and order, while UDP trades that for speed.",
      ["TCP is reliable.", "UDP is fast."], ["Explain the difference out loud"], 0),
    S("Resume tips for new graduates", "article", "life", "do at work", ["Careers"],
      "Lead with projects, quantify outcomes and keep it to one page.",
      ["Numbers make impact concrete."], ["Rewrite two resume bullets"], 1),
]

PROFESSIONAL = [
    S("20-minute lentil dal", "youtube", "life", "cook", ["Cooking"],
      "A weeknight one-pot dal with garlic, cumin and tomatoes.",
      ["Toast the spices first.", "Red lentils cook quickly."],
      ["Buy red lentils and tomatoes", "Cook the dal on Sunday"], 2),
    S("Sheet-pan chicken with vegetables", "article", "life", "cook", ["Cooking"],
      "An easy dinner with one tray and little cleanup.",
      ["Spread the pan so food roasts, not steams."], ["Add chicken to the grocery list"], 1),
    S("Meal prep for busy weeks", "youtube", "life", "try", ["Cooking"],
      "Batch cook grains and proteins on Sunday for quick weekday meals.",
      ["Cook once, eat three times."], ["Prep grains this Sunday"], 1),
    S("Best knife skills for beginners", "youtube", "life", "learn", ["Cooking"],
      "How to hold a chef's knife, and the claw grip that protects your fingers.",
      ["Keep knives sharp."], ["Practice dicing one onion"], 1),
    S("5-minute morning mobility", "instagram", "life", "try", ["Fitness"],
      "A short stretch sequence for hips and lower back, with no equipment.",
      ["Consistency beats intensity."], ["Do the routine before work"], 0),
    S("Beginner dumbbell plan", "article", "life", "try", ["Fitness"],
      "A three day plan with presses, rows and squats.",
      ["Start lighter than you think."], ["Schedule the first session"], 0),
    S("How much cardio do you need?", "youtube", "life", "learn", ["Fitness"],
      "Guidelines on weekly cardio minutes, and easy ways to fit them in.",
      ["Walking counts."], ["Walk 20 minutes at lunch"], 0),
    S("Running shoes compared", "article", "life", "buy", ["Fitness"],
      "Compares budget running shoes on comfort and durability.",
      ["Try shoes later in the day."], ["Try on two pairs"], 0),
    S("Index funds explained", "article", "life", "learn", ["Personal Finance"],
      "Why low-cost index funds suit most long-term investors.",
      ["Fees compound against you."], ["Check the fees on your current fund"], 1),
    S("Building an emergency fund", "article", "life", "try", ["Personal Finance"],
      "Aim for three to six months of expenses, automated in small transfers.",
      ["Automate it."], ["Set up a small monthly transfer"], 1),
    S("Writing better one-on-ones", "article", "work", "do at work", ["Management"],
      "Let the report set the agenda, and end with one clear commitment.",
      ["Their agenda first."], ["Ask for agenda items before Friday's 1:1"], 1),
    S("How to give useful feedback", "youtube", "work", "do at work", ["Management"],
      "Describe the situation, the behavior and its impact, then ask questions.",
      ["Be specific and timely."], ["Give one piece of feedback this week"], 0),
    S("A long read on attention", "article", "life", "just vibes", ["Reading"],
      "An essay on how attention became the scarcest thing we have.",
      ["Attention is finite."], [], 0),
    S("Weekend hiking trails nearby", "reddit", "life", "try", ["Outdoors"],
      "A community list of easy trails within an hour's drive.",
      ["Start early to avoid crowds."], ["Pick a trail for Saturday"], 0),
]

TEAM = [
    S("Client call: Northwind pricing", "text", "work", "do at work", ["Northwind"],
      "Northwind prefers annual billing and asked for a 10 percent discount on a two year term.",
      ["Annual billing preferred.", "Discount requested for two years."],
      ["Send Northwind a revised quote", "Confirm discount limits with finance"], 1),
    S("Northwind support escalation", "text", "work", "do at work", ["Northwind"],
      "Exports time out on large accounts, and they want a named support contact.",
      ["Exports are slow on large accounts."], ["Assign a support contact"], 1),
    S("Sprint 14 planning notes", "text", "work", "do at work", ["Engineering"],
      "The team committed to the billing migration, with API contract review by Thursday.",
      ["Billing migration is the priority."], ["Review the API contract", "Finish billing migration"], 1),
    S("Outage postmortem", "text", "work", "reference", ["Engineering"],
      "An expired certificate caused a 40 minute outage. Automated renewal alerts were agreed.",
      ["Root cause: expired certificate."], ["Add certificate expiry alerts"], 1),
    S("API versioning guide", "article", "work", "reference", ["Engineering"],
      "Compares URL and header versioning, and recommends additive changes first.",
      ["Prefer additive changes."], ["Draft our versioning policy"], 0),
    S("Q1 roadmap review", "text", "work", "do at work", ["Product"],
      "Enterprise SSO is prioritized, and the mobile redesign moves to Q2.",
      ["SSO comes first.", "Mobile redesign is deferred."], ["Update the public roadmap"], 1),
    S("Onboarding drop-off analysis", "pdf", "work", "learn", ["Product"],
      "Most new users stall at the import step, so a sample workspace is proposed.",
      ["Import is the biggest drop-off."], ["Prototype a sample workspace"], 0),
    S("Customer interview notes: Contoso", "text", "work", "reference", ["Product"],
      "Contoso wants audit logs before rolling out to more teams.",
      ["Audit logs are a blocker."], ["Scope audit logs"], 0),
    S("Fundraising deck feedback", "text", "work", "do at work", ["Fundraising"],
      "Advisors asked for a clearer market slide and a tighter story around retention.",
      ["Tighten the retention story."], ["Rewrite the market slide"], 1),
    S("Investor update template", "article", "work", "reference", ["Fundraising"],
      "A monthly format covering metrics, wins, challenges and specific asks.",
      ["Always include a clear ask."], ["Send this month's update"], 0),
    S("Hiring plan: account executive", "text", "work", "do at work", ["Hiring"],
      "One account executive hire is planned, with interviews starting next month.",
      ["Interviews start next month."], ["Publish the job description"], 0),
    S("Interview scorecard", "pdf", "work", "reference", ["Hiring"],
      "A scorecard covering competencies and rating guidance for the panel.",
      ["Score before discussing."], ["Share the scorecard with the panel"], 1),
    S("Competitor teardown", "article", "work", "learn", ["Product"],
      "Compares onboarding and pricing across three direct competitors.",
      ["Competitors gate SSO at higher tiers."], ["Review the pricing comparison"], 0),
]


async def reset_workspace(session, workspace_id):
    await session.execute(text("delete from public.saves where workspace_id = :w"), {"w": workspace_id})
    await session.execute(text("delete from public.tasks where workspace_id = :w"), {"w": workspace_id})
    await session.execute(text("delete from public.topics where workspace_id = :w"), {"w": workspace_id})
    await session.execute(text("delete from public.calendar_events where workspace_id = :w"), {"w": workspace_id})
    await session.execute(text("delete from public.flashcards where workspace_id = :w"), {"w": workspace_id})
    await session.execute(text("delete from public.jobs where payload->>'workspace' = :w"), {"w": str(workspace_id)})


async def add_save(session, workspace_id, user_id, item, age_days):
    created = NOW - timedelta(days=age_days, hours=random.randint(0, 20))
    save_id = uuid4()
    # processed status skips the enqueue trigger, which only fires for pending saves.
    await session.execute(
        text(
            """
            insert into public.saves
              (id, workspace_id, created_by, source_type, title, mode, status, intent,
               intent_source, summary, key_points, raw_text, content_template, language,
               processed_at, created_at)
            values (:id, :w, :u, :source, :title, cast(:mode as public.save_mode), 'ready', :intent,
                    'user', :summary, cast(:points as jsonb), :raw, 'generic', 'en', :at, :at)
            """
        ),
        {
            "id": save_id, "w": workspace_id, "u": user_id, "source": item["source"],
            "title": item["title"], "mode": item["mode"], "intent": item["intent"],
            "summary": item["summary"], "points": json.dumps(item["points"]),
            "raw": f"{item['summary']} " + " ".join(item["points"]), "at": created,
        },  # fmt: skip
    )
    await session.execute(
        text(
            """
            insert into public.save_chunks (save_id, workspace_id, chunk_index, "text")
            values (:s, :w, 0, :t)
            """
        ),
        {"s": save_id, "w": workspace_id, "t": f"{item['title']}. {item['summary']}"},
    )
    for name in item["topics"]:
        topic = await session.scalar(
            text(
                """
                insert into public.topics (workspace_id, name) values (:w, :n)
                on conflict (workspace_id, name) do update set name = excluded.name returning id
                """
            ),
            {"w": workspace_id, "n": name},
        )
        await session.execute(
            text("insert into public.save_topics (save_id, topic_id) values (:s, :t)"),
            {"s": save_id, "t": topic},
        )
    for index, title in enumerate(item["tasks"]):
        finished = index < item["done"]
        at = created + timedelta(days=random.randint(1, 3))
        task = await session.scalar(
            text(
                """
                insert into public.tasks
                  (workspace_id, save_id, title, type, assignee_id, scheduled_for, status, size,
                   followup_at, completed_at, source_agent, created_at)
                values (:w, :s, :title, 'micro_action', :u, :when,
                        cast(:status as public.task_status), 'tiny', :followup, :completed,
                        'seed', :created)
                returning id
                """
            ),
            {
                "w": workspace_id, "s": save_id, "title": title, "u": user_id,
                "when": at if finished else NOW + timedelta(days=random.randint(0, 5)),
                "status": "done" if finished else "accepted",
                "followup": None if finished else NOW + timedelta(days=random.randint(0, 5)),
                "completed": at if finished else None, "created": created,
            },  # fmt: skip
        )
        await session.execute(
            text("insert into public.action_events (task_id, event, \"at\") values (:t, 'accepted', :a)"),
            {"t": task, "a": created},
        )
        if finished:
            await session.execute(
                text("insert into public.action_events (task_id, event, \"at\") values (:t, 'done', :a)"),
                {"t": task, "a": at},
            )
    return save_id


async def seed_workspace(session, workspace_id, user_id, items):
    await reset_workspace(session, workspace_id)
    saves = []
    for item in items:
        saves.append(
            (await add_save(session, workspace_id, user_id, item, random.randint(0, HISTORY_DAYS)), item)
        )
    for save_id, item in saves[:6]:
        if item["points"]:
            await session.execute(
                text(
                    """
                    insert into public.flashcards (save_id, workspace_id, front, back)
                    values (:s, :w, :f, :b)
                    """
                ),
                {
                    "s": save_id, "w": workspace_id,
                    "f": f"What's the key idea of: {item['title']}?", "b": item["points"][0],
                },  # fmt: skip
            )


async def main():
    email = os.environ["DEMO_EMAIL"]
    async with service_session() as session:
        user_id = await session.scalar(
            text("select id from auth.users where lower(email) = lower(:e)"), {"e": email}
        )
        if user_id is None:
            raise SystemExit(f"No user with the email {email}. Create it in Supabase Auth first.")
        personal = await session.scalar(
            text("select id from public.workspaces where owner_id = :u and type = 'personal'"),
            {"u": user_id},
        )
        team_ids = []
        for name in ["Student", "Startup Team"]:
            workspace = await session.scalar(
                text(
                    """
                    select id from public.workspaces
                    where owner_id = :u and type = 'team' and name = :n
                    """
                ),
                {"u": user_id, "n": name},
            )
            if workspace is None:
                workspace = await session.scalar(
                    text(
                        """
                        insert into public.workspaces (name, type, owner_id)
                        values (:n, 'team', :u) returning id
                        """
                    ),
                    {"n": name, "u": user_id},
                )
            team_ids.append(workspace)
        await session.execute(
            text("update public.workspaces set name = 'Professional' where id = :id"),
            {"id": personal},
        )
        await seed_workspace(session, team_ids[0], user_id, STUDENT)
        await seed_workspace(session, personal, user_id, PROFESSIONAL)
        await seed_workspace(session, team_ids[1], user_id, TEAM)
        await session.execute(
            text(
                """
                insert into public.calendar_events
                  (workspace_id, user_id, title, starts_at, is_deadline)
                values (:w, :u, 'Algorithms final exam', :when, true)
                """
            ),
            {"w": team_ids[0], "u": user_id, "when": NOW + timedelta(hours=20)},
        )
    print(f"Seeded {len(STUDENT) + len(PROFESSIONAL) + len(TEAM)} saves for {email}.")


asyncio.run(main())

// Runs every migration on an in-process Postgres (PGlite + pgvector) and proves
// tenant isolation with real SET ROLE queries. Needs no Docker and no Supabase.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { before, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { PGlite } from "@electric-sql/pglite";
import { vector } from "@electric-sql/pglite-pgvector";

const supabaseDir = fileURLToPath(new URL("..", import.meta.url));
const read = (path) => readFileSync(`${supabaseDir}${path}`, "utf8");

const ALICE = "00000000-0000-4000-8000-00000000000a"; // workspace owner
const BOB = "00000000-0000-4000-8000-00000000000b"; // not a member
const VERA = "00000000-0000-4000-8000-00000000000c"; // viewer
const MIA = "00000000-0000-4000-8000-00000000000d"; // member
const ADAM = "00000000-0000-4000-8000-00000000000e"; // admin

const db = new PGlite({ extensions: { vector } });

/** Run queries as a signed-in user, exactly as a Supabase JWT would. */
async function as(userId, fn) {
  await db.query(`select set_config('request.jwt.claims', $1, false)`, [
    JSON.stringify({ sub: userId }),
  ]);
  await db.exec("set role authenticated");
  try {
    return await fn();
  } finally {
    await db.exec("reset role");
    await db.exec(`select set_config('request.jwt.claims', '', false)`);
  }
}

const rows = async (sql, params) => (await db.query(sql, params)).rows;

let workspaceId;
let saveId;

before(async () => {
  await db.exec(read("local/auth_stub.sql"));
  for (const file of readdirSync(`${supabaseDir}migrations`).sort()) {
    await db.exec(read(`migrations/${file}`));
  }
  for (const id of [ALICE, BOB, VERA, MIA, ADAM]) {
    await db.query("insert into auth.users (id) values ($1)", [id]);
  }

  // Alice creates a workspace through RLS, like the real client would.
  [{ id: workspaceId }] = await as(ALICE, () =>
    rows(
      `insert into public.workspaces (name, type, owner_id)
       values ('Team', 'team', $1) returning id`,
      [ALICE],
    ),
  );

  // Set up memberships and a save as the superuser.
  for (const [user, role] of [
    [VERA, "viewer"],
    [MIA, "member"],
    [ADAM, "admin"],
  ]) {
    await db.query(
      `insert into public.workspace_members (workspace_id, user_id, role) values ($1, $2, $3)`,
      [workspaceId, user, role],
    );
  }
  [{ id: saveId }] = await rows(
    `insert into public.saves (workspace_id, created_by, source_type, title)
     values ($1, $2, 'text', 'Secret plan') returning id`,
    [workspaceId, ALICE],
  );
});

describe("schema", () => {
  it("enables RLS on every public table", async () => {
    const unprotected = await rows(
      `select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
       where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity`,
    );
    assert.deepEqual(unprotected, []);
  });

  it("creates the HNSW and GIN retrieval indexes", async () => {
    const indexes = await rows(
      `select indexdef from pg_indexes where tablename = 'save_chunks'`,
    );
    assert.ok(indexes.some((i) => /USING hnsw/.test(i.indexdef)));
    assert.ok(indexes.some((i) => /USING gin/.test(i.indexdef)));
  });

  it("supports vector and full-text search on chunks", async () => {
    const embedding = `[${Array(768).fill(0.1).join(",")}]`;
    await db.query(
      `insert into public.save_chunks (save_id, workspace_id, chunk_index, "text", embedding)
       values ($1, $2, 0, 'Graphs and shortest paths', $3)`,
      [saveId, workspaceId, embedding],
    );
    const byVector = await rows(
      `select chunk_index from public.save_chunks
       order by embedding operator(extensions.<=>) $1 limit 1`,
      [embedding],
    );
    assert.equal(byVector.length, 1);
    const byText = await rows(
      `select chunk_index from public.save_chunks where tsv @@ plainto_tsquery('english', 'graph')`,
    );
    assert.equal(byText.length, 1);
  });

  it("keeps updated_at current", async () => {
    await db.query(`update public.saves set updated_at = '2000-01-01' where id = $1`, [saveId]);
    const [{ year }] = await rows(
      `select extract(year from updated_at)::int as year from public.saves where id = $1`,
      [saveId],
    );
    assert.notEqual(year, 2000);
  });

  it("rejects a chunk whose workspace differs from its save's", async () => {
    const [{ id: otherWorkspace }] = await rows(
      `insert into public.workspaces (name, owner_id) values ('Other', $1) returning id`,
      [BOB],
    );
    await assert.rejects(
      db.query(
        `insert into public.save_chunks (save_id, workspace_id, chunk_index, "text")
         values ($1, $2, 1, 'x')`,
        [saveId, otherWorkspace],
      ),
      /foreign key/,
    );
  });

  it("keeps a task when its save is deleted", async () => {
    const [{ id: tempSave }] = await rows(
      `insert into public.saves (workspace_id, source_type) values ($1, 'text') returning id`,
      [workspaceId],
    );
    const [{ id: taskId }] = await rows(
      `insert into public.tasks (workspace_id, save_id, title) values ($1, $2, 'Try it') returning id`,
      [workspaceId, tempSave],
    );
    await db.query(`delete from public.saves where id = $1`, [tempSave]);
    const [task] = await rows(`select save_id, workspace_id from public.tasks where id = $1`, [taskId]);
    assert.equal(task.save_id, null);
    assert.equal(task.workspace_id, workspaceId);
  });
});

describe("tenant isolation", () => {
  it("makes a workspace's creator its owner", async () => {
    const members = await rows(
      `select role from public.workspace_members where workspace_id = $1 and user_id = $2`,
      [workspaceId, ALICE],
    );
    assert.deepEqual(members, [{ role: "owner" }]);
  });

  it("hides everything from a non-member", async () => {
    await as(BOB, async () => {
      assert.deepEqual(await rows(`select id from public.saves where id = $1`, [saveId]), []);
      assert.deepEqual(
        await rows(`select id from public.workspaces where id = $1`, [workspaceId]),
        [],
      );
      assert.deepEqual(
        await rows(`select id from public.save_chunks where save_id = $1`, [saveId]),
        [],
      );
    });
  });

  it("stops a non-member writing into the workspace", async () => {
    await as(BOB, () =>
      assert.rejects(
        rows(`insert into public.saves (workspace_id, source_type) values ($1, 'text')`, [
          workspaceId,
        ]),
        /row-level security/,
      ),
    );
  });

  it("lets a viewer read but not write", async () => {
    await as(VERA, async () => {
      assert.equal((await rows(`select id from public.saves where id = $1`, [saveId])).length, 1);
      await assert.rejects(
        rows(`insert into public.saves (workspace_id, source_type) values ($1, 'text')`, [
          workspaceId,
        ]),
        /row-level security/,
      );
      const updated = await rows(
        `update public.saves set title = 'hacked' where id = $1 returning id`,
        [saveId],
      );
      assert.deepEqual(updated, []);
    });
  });

  it("lets a member write content but not manage members", async () => {
    await as(MIA, async () => {
      const updated = await rows(
        `update public.saves set title = 'Plan v2' where id = $1 returning id`,
        [saveId],
      );
      assert.equal(updated.length, 1);
      await assert.rejects(
        rows(
          `insert into public.workspace_members (workspace_id, user_id, role) values ($1, $2, 'member')`,
          [workspaceId, BOB],
        ),
        /row-level security/,
      );
      const promoted = await rows(
        `update public.workspace_members set role = 'admin' where user_id = $1 returning id`,
        [MIA],
      );
      assert.deepEqual(promoted, []);
    });
  });

  it("stops an admin taking over the workspace", async () => {
    await as(ADAM, async () => {
      await assert.rejects(
        rows(`update public.workspace_members set role = 'owner' where user_id = $1`, [ADAM]),
        /row-level security/,
      );
      const demoted = await rows(
        `update public.workspace_members set role = 'viewer' where user_id = $1 returning id`,
        [ALICE],
      );
      assert.deepEqual(demoted, []);
      const removed = await rows(
        `delete from public.workspace_members where user_id = $1 returning id`,
        [ALICE],
      );
      assert.deepEqual(removed, []);
      await assert.rejects(
        rows(`update public.workspaces set owner_id = $1 where id = $2`, [ADAM, workspaceId]),
        /permission denied/,
      );
      const deleted = await rows(`delete from public.workspaces where id = $1 returning id`, [
        workspaceId,
      ]);
      assert.deepEqual(deleted, []);
    });
  });

  it("lets an admin rename the workspace", async () => {
    await as(ADAM, async () => {
      const renamed = await rows(
        `update public.workspaces set name = 'Squad' where id = $1 returning id`,
        [workspaceId],
      );
      assert.equal(renamed.length, 1);
    });
  });

  it("keeps conversations private within a workspace", async () => {
    const [{ id: conversationId }] = await as(MIA, () =>
      rows(
        `insert into public.conversations (workspace_id, user_id, title)
         values ($1, $2, 'Private question') returning id`,
        [workspaceId, MIA],
      ),
    );
    await as(MIA, () =>
      rows(`insert into public.messages (conversation_id, role, content) values ($1, 'user', 'hi')`, [
        conversationId,
      ]),
    );
    await as(ADAM, async () => {
      assert.deepEqual(
        await rows(`select id from public.conversations where id = $1`, [conversationId]),
        [],
      );
      assert.deepEqual(
        await rows(`select id from public.messages where conversation_id = $1`, [conversationId]),
        [],
      );
      await assert.rejects(
        rows(`insert into public.messages (conversation_id, role, content) values ($1, 'user', 'x')`, [
          conversationId,
        ]),
        /row-level security/,
      );
    });
  });

  it("never exposes service-only tables to clients", async () => {
    await db.query(`insert into public.api_keys (user_id, hashed_key, label) values ($1, 'h', 'k')`, [
      ALICE,
    ]);
    await as(ALICE, async () => {
      for (const table of ["api_keys", "connected_accounts", "jobs", "agent_runs"]) {
        assert.deepEqual(await rows(`select id from public.${table}`), [], table);
      }
      await assert.rejects(
        rows(`insert into public.jobs (type) values ('steal')`),
        /row-level security/,
      );
    });
  });

  it("denies the anon role outright", async () => {
    await db.exec("set role anon");
    try {
      await assert.rejects(rows(`select id from public.saves`), /permission denied/);
    } finally {
      await db.exec("reset role");
    }
  });

  it("lets the service role through", async () => {
    await db.exec("set role service_role");
    try {
      assert.equal((await rows(`select id from public.saves where id = $1`, [saveId])).length, 1);
    } finally {
      await db.exec("reset role");
    }
  });
});

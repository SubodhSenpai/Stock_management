/**
 * End-to-end smoke test: the frontend, the API, and the session that joins them.
 *
 * Start both servers, then:
 *
 *     node scripts/smoke.mjs
 *
 * This drives real HTTP against both processes. Nothing is mocked, so a pass means the
 * route guard, the cookie handling and the CORS configuration actually work together —
 * the three things that are fine in isolation and broken in combination.
 *
 * Exits non-zero if any check fails, so it can gate a deploy.
 */

const WEB = process.env.SMOKE_WEB_URL ?? "http://localhost:3000";
const API = process.env.SMOKE_API_URL ?? "http://localhost:8000/api/v1";
const LOGIN = { login_id: "manager1", password: "Manager@123" };

const results = [];

function check(name, passed, detail = "") {
  results.push({ name, passed, detail });
  const mark = passed ? "PASS" : "FAIL";
  console.log(`${mark}  ${name}${detail ? `  (${detail})` : ""}`);
}

/** Collect the cookies a response sets, so later requests can present them. */
function cookiesFrom(response) {
  return response.headers
    .getSetCookie()
    .map((cookie) => cookie.split(";")[0])
    .join("; ");
}

async function main() {
  console.log(`Frontend ${WEB}\nAPI      ${API}\n`);

  // --- the app is reachable at all -------------------------------------------------
  let health;
  try {
    health = await fetch(`${API}/health`);
  } catch {
    console.error(`\nCannot reach the API at ${API}. Start it first.`);
    process.exit(1);
  }
  const healthBody = await health.json();
  check("API health", health.ok && healthBody.database === "ok", JSON.stringify(healthBody));

  // --- signed out ------------------------------------------------------------------
  const anon = await fetch(`${WEB}/dashboard`, { redirect: "manual" });
  const anonTarget = anon.headers.get("location") ?? "";
  check(
    "signed-out visitor is sent to /login",
    anon.status === 307 && anonTarget.includes("/login"),
    `${anon.status} -> ${anonTarget}`,
  );

  check(
    "the sign-in page renders",
    (await fetch(`${WEB}/login`)).ok,
    "GET /login",
  );

  // The server is the boundary, not the middleware: ask the API directly with no cookie.
  const unauthorised = await fetch(`${API}/operations`);
  const unauthorisedBody = await unauthorised.text();
  check(
    "the API refuses an anonymous read and returns no data",
    unauthorised.status === 401 && !unauthorisedBody.includes('"items"'),
    `${unauthorised.status}, ${unauthorisedBody.length} bytes`,
  );

  // --- signing in ------------------------------------------------------------------
  const login = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: WEB },
    body: JSON.stringify(LOGIN),
  });
  const cookies = cookiesFrom(login);
  check(
    "sign-in succeeds and sets both cookies",
    login.ok && cookies.includes("access_token") && cookies.includes("refresh_token"),
    login.ok ? "access_token + refresh_token" : `status ${login.status}`,
  );

  check(
    "CORS allows the browser origin to send credentials",
    login.headers.get("access-control-allow-credentials") === "true" &&
      login.headers.get("access-control-allow-origin") === WEB,
    `${login.headers.get("access-control-allow-origin")}`,
  );

  if (!login.ok) {
    console.error("\nCannot sign in. Has the database been seeded (python -m scripts.seed)?");
    return finish();
  }

  const signedIn = { cookie: cookies };

  // --- signed in -------------------------------------------------------------------
  const pages = [
    ["/dashboard", "Dashboard"],
    ["/operations/receipts", "Receipts"],
    ["/operations/deliveries", "Delivery Orders"],
    ["/operations/transfers", "Internal Transfers"],
    ["/operations/adjustments", "Inventory Adjustments"],
    ["/products", "Products"],
    ["/stock", "Stock"],
    ["/moves", "Move History"],
    ["/settings/warehouses", "Warehouses"],
    ["/settings/locations", "Locations"],
    ["/settings/contacts", "Contacts"],
    ["/profile", "Profile"],
  ];

  for (const [path, expected] of pages) {
    const response = await fetch(`${WEB}${path}`, { headers: signedIn });
    const html = await response.text();
    check(
      `${path} renders`,
      response.ok && html.includes(expected),
      response.ok ? `contains "${expected}"` : `status ${response.status}`,
    );
  }

  // A signed-in user should not be left sitting on the sign-in page.
  const loginWhileSignedIn = await fetch(`${WEB}/login`, {
    headers: signedIn,
    redirect: "manual",
  });
  check(
    "signed-in visitor is sent away from /login",
    loginWhileSignedIn.status === 307 &&
      (loginWhileSignedIn.headers.get("location") ?? "").includes("/dashboard"),
    `${loginWhileSignedIn.status}`,
  );

  // --- the data the pages depend on ------------------------------------------------
  const endpoints = [
    ["/auth/me", (data) => data.login_id === LOGIN.login_id],
    ["/dashboard/summary", (data) => Array.isArray(data.cards) && data.cards.length === 4],
    ["/operations?page_size=5", (data) => Array.isArray(data.items)],
    ["/stock?page_size=5", (data) => Array.isArray(data.items)],
    ["/moves?limit=5", (data) => Array.isArray(data.items) && "next_cursor" in data],
    ["/products?page_size=5", (data) => Array.isArray(data.items)],
    ["/locations?type=internal", (data) => Array.isArray(data) && data.length > 0],
  ];

  for (const [path, valid] of endpoints) {
    const response = await fetch(`${API}${path}`, { headers: signedIn });
    const data = response.ok ? await response.json() : null;
    check(`GET ${path}`, response.ok && valid(data), response.ok ? "shape ok" : `status ${response.status}`);
  }

  // --- the contract the UI is built on ---------------------------------------------
  const operations = await (await fetch(`${API}/operations?page_size=1`, { headers: signedIn })).json();
  const first = operations.items?.[0];
  if (first) {
    const detail = await (await fetch(`${API}/operations/${first.id}`, { headers: signedIn })).json();
    check(
      "a document carries allowed_actions",
      Array.isArray(detail.allowed_actions),
      `${detail.reference}: [${detail.allowed_actions?.join(", ")}]`,
    );
    check(
      "its lines carry availability",
      detail.lines?.every((line) => "is_available" in line && "available_quantity" in line),
      `${detail.lines?.length} line(s)`,
    );
  } else {
    check("a document carries allowed_actions", false, "no documents; seed the database");
  }

  // An unknown field must be rejected rather than quietly ignored.
  const smuggled = await fetch(`${API}/users/me`, {
    method: "PATCH",
    headers: { ...signedIn, "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: "Smoke Test", role: "manager" }),
  });
  check(
    "unknown fields are rejected, not ignored",
    smuggled.status === 422,
    `status ${smuggled.status}`,
  );

  finish();
}

function finish() {
  const failed = results.filter((result) => !result.passed);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed.`);
  if (failed.length > 0) {
    console.log("\nFailed:");
    for (const result of failed) console.log(`  - ${result.name} ${result.detail}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

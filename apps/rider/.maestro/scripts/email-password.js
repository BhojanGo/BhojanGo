// The password for the Email tab's sign-in (sign-in-email.yaml). Maestro can't parse this
// as an inline expression, so it lives here. PASSWORD overrides; on hosted QA the seed's
// random passwords come in as QA_PASSWORDS (tools/railway/maestro-qa.sh); locally the seed's.
var who = (typeof EMAIL !== "undefined" && EMAIL) ? EMAIL : "rider1.hyd@example.com";
var qa = (typeof QA_PASSWORDS !== "undefined" && QA_PASSWORDS) ? JSON.parse(QA_PASSWORDS) : {};
output.password = (typeof PASSWORD !== "undefined" && PASSWORD) ? PASSWORD : (qa[who] || "BhojanGo123");

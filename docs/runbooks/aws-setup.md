# AWS setup (one time)

What this sets up: the Terraform state bucket, its lock table, and the GitHub
OIDC roles that let GitHub Actions deploy without stored AWS keys. After this,
merges to `dev` deploy to **staging** and `v*` tags deploy to **prod** after
your approval. Until step 4 is done, those deploy jobs are skipped, not failed.

Commands assume a bash shell (Git Bash, WSL, macOS or Linux) in the repo root.
Region: `us-east-1` (change `AWS_REGION` and `envs/*/backend.hcl` together
if you pick another).

## 1. AWS account(s)

**Recommended:** two accounts, so staging can never touch prod data.
**Fine for the pilot:** one account holding both.

1. Sign up at <https://aws.amazon.com> (this becomes the management account). Turn on MFA for the root user, and don't use root after this step.
2. *Two accounts only:* in **AWS Organizations**, create two member accounts, e.g. `bhojango-staging` and `bhojango-prod`.
3. In **IAM Identity Center**, create a user for yourself with the `AdministratorAccess` permission set on each account you'll use.
4. Install the AWS CLI v2 and sign in for each account:
   ```bash
   aws configure sso          # profile names, e.g. bhojango-staging and bhojango-prod
   aws sts get-caller-identity --profile bhojango-staging
   ```
5. In **Billing → Budgets**, create a monthly budget with an email alert (staging is roughly $180–220/month as sized; see Costs).

## 2. Bootstrap each account (state bucket, lock table, OIDC roles)

Run once **per account**. `environments` lists what that account hosts:
`["staging"]`, `["prod"]`, or `["staging","prod"]` for a single account.
This uses Terraform in Docker, so you don't need to install it.

```bash
PROFILE=bhojango-staging          # then repeat with bhojango-prod
ENVS='["staging"]'                # ["prod"] for prod, ["staging","prod"] if one account
eval "$(aws configure export-credentials --profile "$PROFILE" --format env)"

cd infra/terraform/bootstrap
TF="docker run --rm -it -v $(pwd -W 2>/dev/null || pwd):/tf -w /tf \
    -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN -e AWS_REGION=us-east-1 \
    hashicorp/terraform:1.17.2"
MSYS_NO_PATHCONV=1 $TF init
MSYS_NO_PATHCONV=1 $TF apply -var "environments=$ENVS"
MSYS_NO_PATHCONV=1 $TF output
```

Note the outputs: `tf_state_bucket` and `role_arns` (`<env>-plan` and `<env>-deploy`).

Then keep the bootstrap's local state with the account (it's git-ignored), and remove the local copy:

```bash
aws s3 cp terraform.tfstate "s3://$(MSYS_NO_PATHCONV=1 $TF output -raw tf_state_bucket)/bootstrap/terraform.tfstate" --profile "$PROFILE"
rm -f terraform.tfstate terraform.tfstate.backup
cd ../../..
```

## 3. GitHub environments

Repo → **Settings → Environments**:

1. **New environment** `staging`. No rules needed.
2. **New environment** `production`:
   - **Required reviewers:** add yourself. Every prod deploy and prod `terraform apply` waits for your approval.
   - **Deployment branches and tags:** "Selected branches and tags", add the tag rule `v*`, and the branch `dev` (for the manual Terraform apply workflow).

## 4. GitHub repository variables (no secrets needed)

Repo → **Settings → Secrets and variables → Actions → Variables → New repository variable**:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `us-east-1` |
| `STAGING_TF_STATE_BUCKET` | `tf_state_bucket` from the staging bootstrap |
| `AWS_STAGING_PLAN_ROLE_ARN` | `role_arns["staging-plan"]` |
| `AWS_STAGING_DEPLOY_ROLE_ARN` | `role_arns["staging-deploy"]` |
| `PROD_TF_STATE_BUCKET` | `tf_state_bucket` from the prod bootstrap (same bucket if one account) |
| `AWS_PROD_PLAN_ROLE_ARN` | `role_arns["prod-plan"]` |
| `AWS_PROD_DEPLOY_ROLE_ARN` | `role_arns["prod-deploy"]` |

GitHub OIDC means **no AWS keys are stored in GitHub**. If old secrets
`AWS_ACCOUNT_ID` or `AWS_DEPLOY_ROLE_ARN` exist under *Secrets*, delete them; nothing uses them.

## 5. Create staging

1. **Actions → Terraform apply → Run workflow**, environment `staging`. The first apply takes roughly 20–30 minutes (RDS and ElastiCache are the slow parts).
2. Fill the app secrets in Secrets Manager. Terraform creates them with `SET_ME` placeholders and never overwrites them. Use **test-mode** keys for staging:
   ```bash
   aws secretsmanager put-secret-value --profile bhojango-staging --secret-id bhojango-staging/stripe \
     --secret-string '{"secret_key":"sk_test_...","webhook_secret":"whsec_..."}'
   aws secretsmanager put-secret-value --profile bhojango-staging --secret-id bhojango-staging/razorpay \
     --secret-string '{"key_id":"rzp_test_...","key_secret":"...","webhook_secret":"..."}'
   aws secretsmanager put-secret-value --profile bhojango-staging --secret-id bhojango-staging/twilio \
     --secret-string '{"account_sid":"AC...","auth_token":"...","from_number_us":"+1...","from_number_in":"+91..."}'
   aws secretsmanager put-secret-value --profile bhojango-staging --secret-id bhojango-staging/sendgrid \
     --secret-string '{"api_key":"SG...."}'
   aws secretsmanager put-secret-value --profile bhojango-staging --secret-id bhojango-staging/firebase \
     --secret-string '{"project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...","client_email":"...@....iam.gserviceaccount.com"}'
   ```
   The services start with placeholders; only OTP, payments, email and push need the real values.
   US sales tax uses the same Stripe key: in the Stripe dashboard turn on **Stripe Tax** and add
   your tax registrations (e.g. Idaho) before taking US orders.
3. **Actions → CI/CD Pipeline → Run workflow** on `dev` (or merge anything into `dev`). The *Staging* job builds the images, runs the migrations and rolls out the three services.
4. Check it:
   ```bash
   ALB=$(aws ssm get-parameter --profile bhojango-staging --name /bhojango-staging/deploy/alb_dns_name --query Parameter.Value --output text)
   curl -s "http://$ALB/health"                       # core-api
   curl -s "http://$ALB/api/v1/restaurants?limit=1"   # empty list until staging is seeded
   ```

## 6. Create prod

1. **Actions → Terraform apply → Run workflow**, environment `prod`, then approve it.
2. Fill the prod secrets as in 5.2 with `--profile bhojango-prod`, `bhojango-prod/...` and **live** keys.
3. Release: tag a commit that's already on staging, then approve the *Production* job:
   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   ```

## 7. Later: your domain and HTTPS

1. Request an ACM certificate in `us-east-1` for your API domain (e.g. `api.staging.<domain>`) and validate it with DNS.
2. Set `certificate_arn` and `cors_origins` (your web and admin URLs) in `infra/terraform/envs/<env>/variables.tf` (or a git-ignored `terraform.tfvars`), open a PR, then run **Terraform apply**.
3. Point a DNS record (CNAME/alias) at the ALB name from step 5.4. Until then, the ALB serves plain HTTP.

## Costs (rough, us-east-1 list prices; check the AWS Pricing Calculator)

- **Staging, as sized:** about $180–220/month. Main items: RDS `db.t4g.medium`, ElastiCache `cache.t4g.medium`, one NAT gateway, the ALB, WAF, and Fargate Spot tasks.
- **Prod, as sized:** about $1,200+/month. Main items: Multi-AZ RDS `db.r6g.large`, 3 × `cache.r7g.large`, 3 NAT gateways, and 2+ tasks per service. Before launch, consider smaller prod sizes for the pilot in `modules/rds`, `modules/redis` and `modules/ecs`.

# Public release preparation

This edition generalizes a private scheduling project into a reusable software demonstration.

## Removed or replaced

- The original salon name, logo files, location, telephone number, social links, structured business data, and business ownership claims.
- Marketing copy describing a real salon and notes documenting its research or live deployment.
- Supplied logo imagery, location photography, and third-party stylist portraits.
- Business-specific image/project names, updater labels, and log directories.

The scheduler uses fictional starter stylist names. Clients and appointments start empty. All browser illustrations and brand marks in this edition are original SVG/CSS examples. Email addresses in automated tests use reserved example domains.

The app remains unauthenticated; this preparation does not convert it into a secure public client portal. Do not include real customer records in a public demo.

## Clean history and repository visibility

`public-ready` is an independent root commit with no parents from the original deployment history. It is prepared on a separate branch so the original repository’s `main` branch and automatic production updater remain unchanged.

**The original repository must remain private while its other branches, tags, or accessible historical records retain the original business material. Publishing only a clean default branch does not hide other branches.**

The intended next step is to export this clean branch to a separate repository as its `main` branch, then choose a reuse license and review that destination before making it public. For example, from an independent clone checked out to this branch:

```sh
# PUBLIC_REPOSITORY_URL must identify a new, empty repository you control.
git push "$PUBLIC_REPOSITORY_URL" public-ready:main
```

Push only the clean branch. Do not use `--mirror`, `--all`, or push the original tags/history. Do not redirect the original deployment’s remote or updater to the public demo repository.

## Review scope

The release tree is checked for the original identity/contact markers, accidentally tracked runtime data and credentials, real-business links, and unapproved image assets. The new clean history is secret-scanned. Application tests and isolated local/demo previews use fresh databases with no SMTP configuration.

Review of this branch does not certify the original repository’s Issues, pull requests, Actions artifacts, release attachments, or old Git history. A public release must also respect applicable code ownership and licensing decisions; no license or business authorization is inferred by this cleanup.

## Preparation verification

The generalized release passed 17 backend/updater tests in the Python Docker image. Both demo services reached healthy status in an isolated Compose project with fresh storage and SMTP disabled. Desktop and mobile browser checks covered navigation, the appointment editor, empty client/appointment records, local assets, stylesheet application, and horizontal overflow. The staged release and independent commit history were scanned with Gitleaks; no credential-pattern matches were found. These checks do not certify the app as a production-ready public service.

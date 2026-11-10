# Studio Demo — fictional salon website

A static marketing template accompanying Salon Scheduler. All identities, stylist profiles, service descriptions, and artwork are demo content. It contains no real salon identity, address, telephone number, social account, booking destination, or third-party portrait photographs.

## Preview

From the repository root:

```sh
python3 -m http.server 18094 --bind 127.0.0.1 --directory Website/public
```

Open http://127.0.0.1:18094. Choose a different port if necessary.

Use the root Compose stack’s `website` profile to run the app and website together, or run `docker compose up -d --build --wait` from this folder for the website alone. Both examples use loopback port 18094, so do not run them simultaneously on the same port.

The website is independent of the staff scheduler. No contact form or appointment request is submitted. The contact section explains where a future owner can put verified business information.

## Customize

Edit `public/index.html`, `public/styles.css`, and `public/app.js`. Add only approved contact details, business claims, and imagery. Replace fictional profile text before representing a real team. The abstract botanical illustration and favicon are code-native SVGs; no stock-photo download or external font request is required.

nginx provides a strict same-origin Content Security Policy with no inline script allowance. There is no real-business JSON-LD or tracking script. Revisit those settings deliberately if adding external integrations.

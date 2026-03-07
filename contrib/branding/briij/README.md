# Briij by TextRP branding guide

This directory contains placeholder templates and configuration snippets to rebrand
Synapse for Briij by TextRP. Replace the placeholder URLs and colors with your
production assets.

## Configure Synapse

Add the following to your `homeserver.yaml` (adjust values for your environment):

```yaml
server_name: "briij.example"
public_baseurl: "https://chat.briij.example/"

templates:
  custom_template_directory: /path/to/textrpv2-synapse/contrib/branding/briij/templates

email:
  app_name: "Briij by TextRP"
  notif_from: "Briij by TextRP <noreply@briij.example>"
  subjects:
    password_reset: "[%(server_name)s] Briij by TextRP password reset"
    email_validation: "[%(server_name)s] Validate your Briij by TextRP email"

invite_client_location: "https://app.briij.example"
```

## Templates

The templates in `contrib/branding/briij/templates` override the defaults. Update
these placeholder image URLs to your Briij by TextRP assets:

- `templates/_base.html`
- `templates/notif_mail.html`
- `templates/notice_expiry.html`

## Colors

Update the placeholder colors in these files to match Briij by TextRP branding:

- `templates/mail.css`
- `templates/mail-Briij.css`
- `templates/sso.css`
- `templates/style.css`

## Notes

- `server_name` cannot be changed after first boot. Choose the Briij domain up front.
- Matrix protocol endpoints and spec references must remain unchanged.

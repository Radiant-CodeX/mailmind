# Google / Gmail Setup — make Quick Login + Gmail work live

MailMind works with Gmail accounts at full parity with Outlook (inbox, sent,
drafts, spam, trash, send, reply, trash, restore). In **mock mode** it works with
zero config. To go **live** against real Gmail, create a Google OAuth client and
enable the Gmail API.

## 1. Create a Google Cloud project
1. Go to <https://console.cloud.google.com/>
2. Top bar → project dropdown → **New Project** → name it (e.g. `MailMind`) → **Create**

## 2. Enable the Gmail API
1. **APIs & Services → Library**
2. Search **Gmail API** → **Enable**
3. (Optional, for nicer display name) also enable **People API**

## 3. Configure the OAuth consent screen
1. **APIs & Services → OAuth consent screen**
2. User type: **External** → **Create**
3. Fill app name, user support email, developer email → **Save and Continue**
4. **Scopes** → **Add or Remove Scopes** → add:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `openid`
5. **Test users** → add the Gmail address(es) you'll sign in with (required while
   the app is in "Testing" mode) → **Save**

## 4. Create the OAuth Client ID
1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. **Authorized redirect URIs** → add exactly:
   ```
   http://localhost:8000/api/auth/google/callback
   ```
   (for production, also add `https://api.your-domain.com/api/auth/google/callback`)
4. **Create** → copy the **Client ID** and **Client secret**

## 5. Add to backend `.env`
```ini
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxxxxx
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
```
> The `GOOGLE_REDIRECT_URI` must match the redirect URI registered in step 4 **exactly**.

## 6. Try it
1. Start backend + frontend.
2. On the login screen, type a Gmail address and click **Next** (or click **Continue with Google**).
3. A popup opens Google's consent screen → approve.
4. The popup closes and you land in MailMind showing your real Gmail inbox.

## How it behaves
- **Provider auto-detection:** `@gmail.com` / `@googlemail.com` → Google; everything else → Microsoft.
- **Quick Login:** after you sign in once and sign out, the refresh token is reused
  to resume silently (no consent again) for up to a week.
- **Tokens:** the Google refresh token is stored in `backend/data/google_token.json`
  (gitignored — never commit it).

## Notes & limits
- While the consent screen is in **Testing** mode, only the **Test users** you added
  can sign in. Publish the app to allow anyone.
- Gmail labels map to folders: `INBOX`, `SENT`, `DRAFT`, `SPAM`, `TRASH`.
- Calendar/Tasks commitment creation currently targets Microsoft Graph; Gmail
  parity covers **mail** operations.

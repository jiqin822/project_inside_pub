# STT 403: Permission speech.recognizers.recognize denied

If you see:

```text
403 Permission 'speech.recognizers.recognize' denied on resource (or it may not exist).
[reason: "IAM_PERMISSION_DENIED" ... "permission" value: "speech.recognizers.recognize"]
```

the service account used by the backend (from `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_APPLICATION_CREDENTIALS_JSON`) does not have the right IAM role on the **same GCP project** that owns the recognizer.

## 1. Confirm project and service account

- **Project**: From `STT_RECOGNIZER`, e.g. `projects/940733179670/locations/us/recognizers/livecoach` → project **number** `940733179670` (or use your project **ID**, e.g. `project-inside-485919`).
- **Service account**: From your JSON key: `client_email`, e.g. `project-inside@project-inside-485919.iam.gserviceaccount.com`.  
  The backend uses this SA; the role must be granted to **this** principal.

## 2. Grant the role at **project** level

IAM for Speech-to-Text is managed at the **project**. Grant **Cloud Speech Client** to that service account on the **same project** as the recognizer.

Using **project ID** (recommended):

```bash
# Replace PROJECT_ID and SERVICE_ACCOUNT_EMAIL with your values
export PROJECT_ID=project-inside-485919
export SERVICE_ACCOUNT_EMAIL=project-inside@project-inside-485919.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/speech.client"
```

Using **project number** (if you use it in `STT_RECOGNIZER`):

```bash
gcloud projects add-iam-policy-binding 940733179670 \
  --member="serviceAccount:project-inside@project-inside-485919.iam.gserviceaccount.com" \
  --role="roles/speech.client"
```

Role **name** in Console: **Cloud Speech-to-Text Client** (role id: `roles/speech.client`).  
It includes `speech.recognizers.recognize`, `recognizers.get`, `recognizers.list`, etc.

## 3. Verify the binding

```bash
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role,bindings.members)"
```

Then look for your service account email and `roles/speech.client` in the output. Or:

```bash
gcloud projects get-iam-policy PROJECT_ID --format=json | grep -A1 "speech.client"
```

You should see `roles/speech.client` and your SA email.

## 4. If 403 persists

- **Wait 1–2 minutes** for IAM propagation.
- **Confirm project**: Recognizer and IAM must be in the **same** project. `STT_RECOGNIZER` uses `projects/940733179670/...` → bind the role on project **940733179670** (or the project ID that corresponds to it).
- **Confirm SA**: Backend must use the same key whose `client_email` you granted the role. No typo in the email.
- **Broader role (test only)**: To rule out a role quirk, temporarily grant **Cloud Speech Administrator** (`roles/speech.admin`) on the project to the same SA. If 403 goes away, the issue was the client role not yet applied; you can then try re-adding only `roles/speech.client` and remove `roles/speech.admin` if desired.

## 5. Resource vs project

The error says “permission denied on resource”; the **resource** is the recognizer (e.g. `projects/.../recognizers/livecoach`). Permission is still granted at the **project** (or parent) level. Granting **Cloud Speech Client** on the **project** that contains that recognizer is sufficient; you do not need a separate binding on the recognizer resource itself.

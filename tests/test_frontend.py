from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_convene_stops_voice_before_submitting():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "function stopVoiceForSubmit()" in html
    assert "if(voiceListening)stopVoiceForSubmit();" in html
    assert "voiceInterim" in html
    assert "document.getElementById('convene').onclick=convene;" in html


def test_frontend_is_self_contained_and_does_not_embed_secrets():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" not in html
    assert 'id="dilemma"' in html
    assert 'id="voiceBtn"' in html
    assert 'id="convene"' in html


def test_convene_runtime_state_is_explicitly_declared():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "let running=false;" in html
    assert "let mode='quick';" in html
    assert "let rounds=0;" in html
    assert "const state=document.getElementById('roundState');" in html
    assert "const log=document.getElementById('logList');" in html
    assert "const order=agents.map(a=>a.id);" in html


def test_convene_runtime_helpers_exist():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "function pulseAgent(id)" in html
    assert "function addLog(agent,message)" in html
    assert "function pick(items)" in html


def test_private_council_file_upload_list_download_and_remove_are_wired():
    html = FRONTEND.read_text(encoding="utf-8")
    assert 'id="councilFileInput"' in html
    assert "storage.from(storageBucket).upload(path,file" in html
    assert "storage.from(storageBucket).list(currentUser.id" in html
    assert "storage.from(storageBucket).download(path)" in html
    assert "storage.from(storageBucket).remove([path])" in html
    assert "const MAX_DOCUMENT_BYTES=20*1024*1024;" in html
    assert "function newStorageId()" in html
    assert "${newStorageId()}__${safeStorageName(file.name)}" in html
    assert "function storageErrorMessage(err,action='upload')" in html
    assert "Storage bucket “${storageBucket}” was not found." in html
    assert "apply the owner-only policies in supabase/council_files_storage.sql" in html


def test_auth_uses_explicit_input_references_and_preserves_restored_session():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "const loginEmailInput=document.getElementById('loginEmail');" in html
    assert "const registerPasswordInput=document.getElementById('registerPassword');" in html
    assert "Do not discard a valid Supabase session" in html


def test_workspace_uses_per_mode_state_and_captured_payloads():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "const workspaceState=Object.fromEntries" in html
    assert "input:'',context:'',evidenceUrls:'',result:null,error:null,loading:false,requestId:0" in html
    assert "function saveWorkspaceDraft()" in html
    assert "function renderWorkspaceState(mode=workspaceMode)" in html
    assert "const requestMode=workspaceMode,requestId=++state.requestId;" in html
    assert "body:JSON.stringify(payload)" in html
    assert "state.result=result;state.error=null" in html
    assert "state.error=councilErrorMessage(err)" in html
    assert "if(workspaceMode===requestMode)renderWorkspaceState(requestMode)" in html


def test_workspace_acceptance_case_is_encoded_in_source():
    html = FRONTEND.read_text(encoding="utf-8")
    # The implementation must restore the selected mode's own draft rather
    # than merely clearing the shared textarea on tab changes.
    assert "saveWorkspaceDraft();\n  workspaceMode=next;" in html
    assert "workspaceTaskEl.value=state.input" in html
    assert "workspaceContextEl.value=state.context" in html
    assert "workspaceEvidenceEl.value=state.evidenceUrls" in html


def test_navigation_shortcuts_ignore_editable_fields():
    html = FRONTEND.read_text(encoding="utf-8")
    assert "const editing=target?.matches?.('input,textarea,select,[contenteditable=\"true\"]');" in html
    assert "if(editing)return;" in html

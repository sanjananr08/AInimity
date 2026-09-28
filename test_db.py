import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# CREATE
r = sb.table("evidence").insert({"file_name": "test.pdf", "result": "ok"}).execute()
row_id = r.data[0]["id"]
print("1. INSERT ok, id =", row_id)

# READ
data = sb.table("evidence").select("*").eq("id", row_id).execute().data
assert len(data) == 1
print("2. READ ok:", data)

# UPDATE
sb.table("evidence").update({"result": "updated"}).eq("id", row_id).execute()
data = sb.table("evidence").select("*").eq("id", row_id).execute().data
assert data[0]["result"] == "updated"
print("3. UPDATE ok")

# DELETE
sb.table("evidence").delete().eq("id", row_id).execute()
data = sb.table("evidence").select("*").eq("id", row_id).execute().data
assert len(data) == 0
print("4. DELETE ok")

print("ALL TESTS PASSED")
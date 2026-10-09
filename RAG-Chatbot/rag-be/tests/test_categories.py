"""Document categories: per-profile, assignable to documents, isolated like everything else."""
import pytest


@pytest.fixture()
def two(client):
    for name in ("company1", "company2"):
        client.post("/api/profiles", json={"name": name})
    client.wait()
    return client


def category(c, pid, name):
    r = c.post(f"/api/profiles/{pid}/categories", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def upload(c, pid, filename, text="hello world"):
    r = c.post(f"/api/profiles/{pid}/documents", files={"files": (filename, text.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    c.wait()
    docs = c.get(f"/api/profiles/{pid}/documents").json()["documents"]
    return next(d for d in docs if d["filename"] == filename)


def test_category_crud_and_profile_isolation(two):
    billing = category(two, "company1", "Billing")
    assert billing["name"] == "Billing" and billing["profile_id"] == "company1"
    assert two.post("/api/profiles/company1/categories", json={"name": "billing"}).status_code == 409  # case-insensitive dup
    category(two, "company2", "Billing")  # same name, different profile: fine

    renamed = two.patch(f"/api/profiles/company1/categories/{billing['id']}", json={"name": "Invoices"}).json()
    assert renamed["name"] == "Invoices"

    listing = two.get("/api/profiles/company1/categories").json()["categories"]
    assert [c["name"] for c in listing] == ["Invoices"]
    assert len(two.get("/api/profiles/company2/categories").json()["categories"]) == 1

    # a category id from another profile is not reachable
    other = two.get("/api/profiles/company2/categories").json()["categories"][0]
    assert two.patch(f"/api/profiles/company1/categories/{other['id']}", json={"name": "hacked"}).status_code == 404
    assert two.delete(f"/api/profiles/company1/categories/{other['id']}").status_code == 404

    assert two.delete(f"/api/profiles/company1/categories/{renamed['id']}").status_code == 200
    assert two.get("/api/profiles/company1/categories").json()["categories"] == []


def test_assign_categories_to_documents(two):
    billing = category(two, "company1", "Billing")
    policy = category(two, "company1", "Policy")
    doc = upload(two, "company1", "invoice.txt")

    r = two.patch(f"/api/profiles/company1/documents/{doc['id']}/categories", json={"category_ids": [billing["id"], policy["id"]]})
    assert r.status_code == 200
    assert sorted(r.json()["category_ids"]) == sorted([billing["id"], policy["id"]])

    listed = two.get("/api/profiles/company1/documents").json()["documents"]
    tagged = next(d for d in listed if d["id"] == doc["id"])
    assert sorted(tagged["category_ids"]) == sorted([billing["id"], policy["id"]])

    # replace: dropping one category untags it
    r = two.patch(f"/api/profiles/company1/documents/{doc['id']}/categories", json={"category_ids": [billing["id"]]})
    assert r.json()["category_ids"] == [billing["id"]]

    # a category id from another profile is rejected
    other_doc = upload(two, "company2", "other.txt")
    other_cat = category(two, "company2", "Misc")
    assert two.patch(f"/api/profiles/company1/documents/{doc['id']}/categories", json={"category_ids": [other_cat["id"]]}).status_code == 422
    assert two.patch(f"/api/profiles/company2/documents/{other_doc['id']}/categories", json={"category_ids": [other_cat["id"]]}).status_code == 200


def test_deleting_category_untags_documents_without_deleting_them(two):
    billing = category(two, "company1", "Billing")
    doc = upload(two, "company1", "invoice.txt")
    two.patch(f"/api/profiles/company1/documents/{doc['id']}/categories", json={"category_ids": [billing["id"]]})
    two.delete(f"/api/profiles/company1/categories/{billing['id']}")
    listed = two.get("/api/profiles/company1/documents").json()["documents"]
    tagged = next(d for d in listed if d["id"] == doc["id"])
    assert tagged["category_ids"] == []


def test_category_validation(two):
    assert two.post("/api/profiles/company1/categories", json={"name": ""}).status_code == 422
    assert two.post("/api/profiles/company1/categories", json={"name": "x" * 61}).status_code == 422
    assert two.post("/api/profiles/nope/categories", json={"name": "Billing"}).status_code == 404

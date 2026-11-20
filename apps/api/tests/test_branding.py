from tests.conftest import register, tenant_headers


def test_branding_save_read_and_public_lookup(client):
    a = register(client, "Brand Co")
    h = tenant_headers(a)
    assert client.get("/api/v1/branding", headers=h).json()["app_name"] is None
    r = client.put("/api/v1/branding", headers=h, json={"app_name": "GrowthPro", "primary_color": "#1A73E8",
                                                        "logo_url": "https://cdn.example.com/logo.png",
                                                        "app_domain": "https://App.GrowthPro.in/"})
    assert r.status_code == 200, r.text
    assert r.json()["primary_color"] == "#1a73e8" and r.json()["app_domain"] == "app.growthpro.in"
    pub = client.get("/api/v1/public/branding", params={"domain": "app.growthpro.in"}).json()
    assert pub["app_name"] == "GrowthPro"
    assert client.get("/api/v1/public/branding", params={"domain": "nope.example.com"}).json()["app_name"] is None


def test_branding_validation_and_domain_conflict(client):
    a, b = register(client, "Brand A"), register(client, "Brand B")
    bad = client.put("/api/v1/branding", headers=tenant_headers(a), json={"primary_color": "blue"})
    assert bad.status_code == 422
    assert client.put("/api/v1/branding", headers=tenant_headers(a),
                      json={"logo_url": "http://insecure.example.com/x.png"}).status_code == 422
    ok = client.put("/api/v1/branding", headers=tenant_headers(a), json={"app_domain": "crm.shared.com"})
    assert ok.status_code == 200
    r = client.put("/api/v1/branding", headers=tenant_headers(b), json={"app_domain": "crm.shared.com"})
    assert r.status_code == 409

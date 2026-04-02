import sys
sys.path.insert(0, "/app")
from app.services.dictionary_loader import _extract_vendor_ids, _check_vendor_id_collision
cambium = open("/app/dictionaries/Cambium_450i").read()
vids = _extract_vendor_ids(cambium)
print("Cambium vendors:", vids)
collisions = _check_vendor_id_collision(cambium, [], skip_filename="Cambium_450i")
print("Collisions:", collisions if collisions else "NONE - OK")
cisco_fake = "VENDOR Fake 9\nBEGIN-VENDOR Fake\nATTRIBUTE Fake-Attr 1 integer\nEND-VENDOR Fake"
coll2 = _check_vendor_id_collision(cisco_fake, [], skip_filename="test_fake")
print("Cisco ID 9 collision:", coll2[0] if coll2 else "missed - BUG")

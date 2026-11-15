import unittest
from app.ai.contract import normalize_ai_result
PET="00000000-0000-4000-8000-000000000021"
OTHER="00000000-0000-4000-8000-000000000099"
def result():
 return {"draft":{"pet_ids":[],"service_type":"home_visit","fee_type":None,"window_start":None,"window_end":None,"expected_duration_minutes":None,"location":None,"budget":None,"handover_notes":None,"emergency_contact":None,"requirements":None,"precautions":None,"raw_text":"model","checklist_items":[{"item_key":"feed_food","pet_id":PET,"position":1,"content":"喂食","completion_condition":"完成喂食","required":True}]},"questions":[]}
class ContractTests(unittest.TestCase):
 def test_selected_pet_ids_are_preserved(self):
  x=result();x["draft"]["pet_ids"]=[OTHER];self.assertEqual(normalize_ai_result(x,[PET],"原文")["draft"]["pet_ids"],[PET])
 def test_raw_text_is_preserved(self): self.assertEqual(normalize_ai_result(result(),[PET],"原始输入")["draft"]["raw_text"],"原始输入")
 def test_unselected_checklist_pet_is_rejected(self):
  x=result();x["draft"]["checklist_items"][0]["pet_id"]=OTHER
  with self.assertRaises(ValueError):normalize_ai_result(x,[PET],"原文")
 def test_invalid_time_order_is_rejected(self):
  x=result();x["draft"]["window_start"]="2026-11-16T18:00:00+08:00";x["draft"]["window_end"]="2026-11-16T17:00:00+08:00"
  with self.assertRaises(ValueError):normalize_ai_result(x,[PET],"原文")
 def test_duration_must_fit_window(self):
  x=result();x["draft"]["window_start"]="2026-11-16T14:00:00+08:00";x["draft"]["window_end"]="2026-11-16T14:20:00+08:00";x["draft"]["expected_duration_minutes"]=30
  with self.assertRaises(ValueError):normalize_ai_result(x,[PET],"原文")
if __name__=="__main__":unittest.main()

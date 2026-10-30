"""Offline image + invitation policy regression; no device initialization."""
import json, hashlib, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from module.atom.image import RuleImage
from tasks.base_task import BaseTask
from tasks.GlobalGame.config_emergency import Emergency, FriendInvitation
ROOT = Path(__file__).resolve().parents[3]
GG = ROOT/'tasks/GlobalGame/gg'
class RewardTests(unittest.TestCase):
    def setUp(self):
        self.items={i['itemName']:i for i in json.loads((GG/'image.json').read_text(encoding='utf-8'))}
        self.rules={}
        for name in ('g_jade','g_cat_food','g_dog_food'):
            i=self.items[name]
            self.rules[name]=RuleImage(tuple(map(int,i['roiFront'].split(','))),tuple(map(int,i['roiBack'].split(','))),i['method'],i['threshold'],str(GG/i['imageName']))
    def run_policy(self,reward,policy=FriendInvitation.JADE_AND_FOOD):
        image=np.zeros((720,1280,3),dtype=np.uint8)
        if reward:
            rule=self.rules[reward];x,y,_,_=rule.roi_back;h,w=rule.image.shape[:2];image[y:y+h,x:x+w]=rule.image
        t=BaseTask.__new__(BaseTask)
        t.device=SimpleNamespace(image=image,detect_record=set(),screenshot=Mock())
        t.config=SimpleNamespace(global_game=SimpleNamespace(emergency=Emergency(friend_invitation=policy)))
        t.set_next_run=Mock();t.appear_then_click=Mock(return_value=True)
        reward_map={str(t.I_G_JADE):'g_jade',str(t.I_G_CAT_FOOD):'g_cat_food',str(t.I_G_DOG_FOOD):'g_dog_food'}
        counts={}
        def appear(target,**kw):
            name=str(target)
            if name in reward_map:return self.rules[reward_map[name]].match(image)
            counts[name]=counts.get(name,0)+1
            return counts[name]<=(2 if target==t.I_G_ACCEPT else 1)
        t.appear=Mock(side_effect=appear)
        self.assertTrue(t._burst())
        return t
    def test_cat_asset_is_actual_food_not_generic_shard(self):
        self.assertEqual(hashlib.sha256((GG/'gg_g_cat_food.png').read_bytes()).hexdigest(),'02b1cb7822522b8243fa64f34651e94641642ca8badcf98527593749bf39b9a8')
    def test_allowed_rewards_accept(self):
        for name in self.rules:
            with self.subTest(reward=name):
                t=self.run_policy(name);self.assertEqual(t.appear_then_click.call_args.args[0],t.I_G_ACCEPT);t.set_next_run.assert_called_once()
    def test_unknown_reward_ignored(self):
        t=self.run_policy(None);self.assertEqual(t.appear_then_click.call_args.args[0],t.I_G_IGNORE);t.set_next_run.assert_not_called()
    def test_only_jade_ignores_food(self):
        for name in ('g_cat_food','g_dog_food'):
            with self.subTest(reward=name):
                t=self.run_policy(name,FriendInvitation.ONLY_JADE);self.assertEqual(t.appear_then_click.call_args.args[0],t.I_G_IGNORE);t.set_next_run.assert_not_called()
    def test_only_jade_accepts_jade(self):
        t=self.run_policy('g_jade',FriendInvitation.ONLY_JADE);self.assertEqual(t.appear_then_click.call_args.args[0],t.I_G_ACCEPT)
    def test_cat_coordinates_match_metadata(self):
        r=BaseTask.I_G_CAT_FOOD;i=self.items['g_cat_food']
        self.assertEqual(tuple(r.roi_front),tuple(map(int,i['roiFront'].split(','))))
        self.assertEqual(tuple(r.roi_back),tuple(map(int,i['roiBack'].split(','))))
    def test_templates_fit_roi(self):
        for r in self.rules.values():
            h,w=r.image.shape[:2];self.assertLessEqual(h,r.roi_back[3]);self.assertLessEqual(w,r.roi_back[2])
if __name__=='__main__':unittest.main()

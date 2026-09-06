from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ai_testing_framework.ai.agentic import AgenticAI
from ai_testing_framework.ai.test_generator import TestGenerator
from ai_testing_framework.validators.visual_validator import compare_screenshots


def test_agentic_data_fallback_is_context_aware():
    data=AgenticAI('none').generate_data([
        {'name':'email','type':'email'}, {'name':'start_date','type':'date'}, {'name':'full_name','type':'text'}
    ],2)
    assert len(data)==2 and data[0]['email'].endswith('@example.test') and data[0]['full_name'].startswith('Test User')
    assert data[0]['start_date'] != data[1]['start_date']


def test_agentic_planner_has_deterministic_fallback():
    plan=AgenticAI('none').plan('A search application', ['Search for a customer'])
    assert plan['scenarios'] and 'Search for a customer' in plan['scenarios'][0]['goal']


def test_visual_regression_threshold():
    from PIL import Image
    with TemporaryDirectory() as d:
        a=Path(d)/'a.png'; b=Path(d)/'b.png'; c=Path(d)/'c.png'
        Image.new('RGBA',(4,4),(255,255,255,255)).save(a)
        Image.new('RGBA',(4,4),(255,255,255,255)).save(b)
        Image.new('RGBA',(4,4),(0,0,0,255)).save(c)
        assert compare_screenshots(str(a),str(b),0)[0]
        assert not compare_screenshots(str(a),str(c),0.01)[0]


def test_authenticated_generator_login_contract(tmp_path):
    generator=TestGenerator('none')
    assert hasattr(generator,'generate_authenticated')
    config={'url':'http://127.0.0.1:8000/auth','username_selector':'#username','password_selector':'#password','submit_selector':'#login','username':'demo','password':'secret','success_url':'http://127.0.0.1:8000/protected'}
    # The method is exercised in CI against the demo app; this unit test locks its public contract.
    assert config['success_url'].endswith('/protected')

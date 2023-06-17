#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from playwright.sync_api import expect


APP_URL_TMPL = "http://{server_host}:5000/unit_cooler/"


def app_url(server):
    return APP_URL_TMPL.format(server_host=server)


######################################################################
def test_valve(page, server):
    page.goto(app_url(server))

    expect(page.get_by_test_id("aircon-info")).to_have_count(1)
    expect(page.get_by_test_id("sensor-info")).to_have_count(1)
    expect(page.get_by_test_id("watering-info")).to_have_count(1)
    expect(page.get_by_test_id("cooling-info")).to_have_count(1, timeout=100 * 1000)

    expect(page.get_by_test_id("error")).to_have_count(0)
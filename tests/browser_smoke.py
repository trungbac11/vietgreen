"""Read-only browser checks against an already-started isolated demo stack."""
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://web:8000/', wait_until='networkidle')
    page.get_by_role('heading', name='Understand the Data. See the Evidence.').wait_for()
    data = page.evaluate("fetch('/api/catalog').then(r=>r.json())")
    assert len(data['dim_company']) == 6 and data['summary']['observations'] == 2046
    assert any(d['source_id'] == 'SRC001' and d['company_id'] == 'COM005' for d in data['pipeline_documents'])
    page.goto('http://web:8000/#company/COM005', wait_until='networkidle')
    page.get_by_role('heading', name='Vinamilk').wait_for()
    page.get_by_role('button', name='Reports & Evidence').click()
    page.get_by_text('Clean Label Project - Vinamilk certified product listing', exact=True).wait_for()
    page.get_by_text('Automatically extracted; not reviewed', exact=True).wait_for()
    page.get_by_role('button', name='Overview & metrics').click()
    page.get_by_role('heading', name='Environmental Data Coverage').wait_for()
    assert page.locator('.coverage-item').count() > 0
    page.locator('#metrictable table').wait_for()
    page.locator('.metricrow').first.click()
    assert page.locator('dialog[open]').count() == 1
    page.locator('.close').click()
    # A competing approximate observation in 2021 must exclude that year entirely;
    # the remaining 2020 and 2024 points are positioned according to elapsed time.
    result = page.evaluate("""() => {
      const chart=document.querySelector('#chart');
      const base={metric_id:'test',unit_code:'kg',value_qualifier:'eq'};
      drawChart([{...base,year:2020,value:1},{...base,year:2021,value:2},
                 {...base,year:2021,value:3,value_qualifier:'approx'},
                 {...base,year:2024,value:4}],chart);
      return {points:chart.querySelectorAll('circle').length, note:document.querySelector('#chartnote').textContent};
    }""")
    assert result['points'] == 2 and '2 observations omitted' in result['note'], result
    spacing = page.evaluate("""() => {
      const base={metric_id:'test',unit_code:'kg',value_qualifier:'eq'};
      drawChart([{...base,year:2020,value:1},{...base,year:2021,value:2},
                 {...base,year:2024,value:4}],document.querySelector('#chart'));
      return Array.from(document.querySelectorAll('#chart circle'), p => Number(p.getAttribute('cx')));
    }""")
    assert abs((spacing[1]-spacing[0]) / (spacing[2]-spacing[1]) - 1/3) < 0.001, spacing
    page.goto('http://web:8000/#product/COM005-P002', wait_until='networkidle')
    page.get_by_text('Product-level environmental indicators are not available', exact=False).wait_for()
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto('http://web:8000/#companies', wait_until='networkidle')
    page.locator('#menu').click()
    assert 'open' in page.locator('#sidebar').get_attribute('class')
    assert not errors, errors
    browser.close()
print('PASS: desktop/mobile navigation, API evidence, company/product pages, chart exclusions, evidence dialog')

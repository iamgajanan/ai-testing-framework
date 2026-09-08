# SaaS Acceptance Test Websites

| Suite | Website | Base URL | Coverage | Expected |
|---|---|---|---|---|
| `saucedemo_e2e.json` | SauceDemo | https://www.saucedemo.com | Login, inventory, cart, checkout, locked user | PASS |
| `the_internet_browser_interactions.json` | The Internet | https://the-internet.herokuapp.com | Login, invalid login, checkboxes, dropdown, dynamic loading, upload controls | PASS |
| `automation_exercise_ecommerce.json` | Automation Exercise | https://automationexercise.com | Home, login, invalid login, products, search | PASS |
| `demoqa_widgets_forms.json` | DemoQA | https://demoqa.com | Text box, checkbox, radio, buttons, upload control | PASS |
| `webdriver_university_interactions.json` | WebDriver University | https://webdriveruniversity.com | Contact form, login portal, todo, accordion | PASS |
| `todomvc_state_regression.json` | TodoMVC React | https://todomvc.com/examples/react/dist/ | Create, multiple items, completion, filters | PASS |
| `framework_demo_app_regression.json` | AI Testing Framework Demo App | Local demo app | Framework-owned smoke/regression checks | PASS |
| `intentional_failure_regression.json` | Intentional Failure | Configured target site | Failure reporting and artifact lifecycle | EXPECTED FAIL |

> Public demo sites can change. These suites should be executed against the current site before being treated as permanent production regression assets.

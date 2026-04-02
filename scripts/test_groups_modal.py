from playwright.sync_api import sync_playwright
import sys


def test_groups_modal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to login first
        page.goto("https://localhost/")
        page.wait_for_load_state("networkidle")

        # Check if login page loads
        if (
            "login" in page.url.lower()
            or page.locator('input[type="password"]').count() > 0
        ):
            # Login
            page.fill('input[type="text"]', "admin")
            page.fill('input[type="password"]', "admin123")
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

        # Navigate to Groups page
        page.goto("https://localhost/#/groups")
        page.wait_for_load_state("networkidle")

        print("=== Testing Nuevo Grupo Modal ===")

        # Find the "Nuevo Grupo" button
        nuevo_grupo_btn = page.locator('button:has-text("Nuevo Grupo")')
        if nuevo_grupo_btn.count() > 0:
            print("✓ 'Nuevo Grupo' button found")
            nuevo_grupo_btn.first.click()
            page.wait_for_timeout(500)

            # Check if modal opened
            modal = page.locator("text=Nuevo Grupo").first
            if modal.count() > 0:
                print("✓ Modal opened successfully")

                # Check for input field
                input_field = page.locator('input[placeholder*="mi_nuevo_grupo"]')
                if input_field.count() > 0:
                    print("✓ Input field found with placeholder")

                    # Test input with spaces
                    input_field.fill("test group name")
                    # Verify spaces are replaced with underscores
                    value = input_field.input_value()
                    if "_" in value:
                        print(f"✓ Spaces correctly replaced with underscores: {value}")
                    else:
                        print(f"✗ Spaces NOT replaced: {value}")

                # Check that "Crear" button exists and is disabled initially
                crear_btn = page.locator('button:has-text("Crear")')
                if crear_btn.count() > 0:
                    print("✓ 'Crear' button found")
                    # Check disabled state
                    is_disabled = crear_btn.first.get_attribute("disabled")
                    if is_disabled:
                        print("✓ 'Crear' button is disabled when input is empty")
                    else:
                        print("✗ 'Crear' button should be disabled when input is empty")
            else:
                print("✗ Modal did NOT open")
        else:
            print("✗ 'Nuevo Grupo' button NOT found")

        print("\n=== Testing Attribute Select ===")

        # Click "Agregar Atributo" button if a group is selected
        agregar_attr_btn = page.locator('button:has-text("Agregar Atributo")')
        if agregar_attr_btn.count() > 0 and agregar_attr_btn.first.is_enabled():
            print("✓ 'Agregar Atributo' button found and enabled")
            agregar_attr_btn.first.click()
            page.wait_for_timeout(500)

            # Check for attribute select
            attr_select = page.locator("select").filter(has=page.locator("optgroup"))
            if attr_select.count() > 0:
                print("✓ Attribute select with optgroups found")

                # Check for Sistema and Custom optgroups
                sistema_optgroup = page.locator('optgroup[label="Sistema"]')
                custom_optgroup = page.locator('optgroup[label="Custom"]')

                if sistema_optgroup.count() > 0:
                    print("✓ 'Sistema' optgroup found")
                    sistema_options = sistema_optgroup.locator("option").count()
                    print(f"  → {sistema_options} options in Sistema")
                else:
                    print("✗ 'Sistema' optgroup NOT found")

                if custom_optgroup.count() > 0:
                    print("✓ 'Custom' optgroup found")
                    custom_options = custom_optgroup.locator("option").count()
                    print(f"  → {custom_options} options in Custom")
                else:
                    print(
                        "✗ 'Custom' optgroup NOT found (may be empty if no custom dicts)"
                    )
            else:
                print("✗ Attribute select with optgroups NOT found")
        else:
            print("⚠ 'Agregar Atributo' button not enabled (no group selected)")

        # Take screenshot for verification
        page.screenshot(path="/tmp/groups-test.png", full_page=True)
        print("\n📸 Screenshot saved to /tmp/groups-test.png")

        browser.close()
        print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_groups_modal()

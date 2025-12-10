import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from app import app, db
from app.modules.community.models import Community, CommunityDatasetProposal
from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def clean_all_communities():
    with app.app_context():
        try:
            communities = Community.query.all()
            for community in communities:
                community.curators = []
                CommunityDatasetProposal.query.filter_by(community_id=community.id).delete(synchronize_session="fetch")
                db.session.delete(community)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


def _login_driver(driver, host, email, password):
    driver.get(f"{host}/login")
    email_field = driver.find_element(By.NAME, "email")
    password_field = driver.find_element(By.NAME, "password")
    email_field.clear()
    password_field.clear()
    email_field.send_keys(email)
    password_field.send_keys(password)
    password_field.send_keys(Keys.RETURN)
    time.sleep(1)


class TestCommunities:

    def setup_method(self, method):
        clean_all_communities()
        self.driver = initialize_driver()
        self.host = get_host_for_selenium_testing()
        self.vars = {}
        self.driver.maximize_window()
        _login_driver(self.driver, self.host, "user1@example.com", "1234")

    def teardown_method(self, method):
        close_driver(self.driver)

    def test_create_communities_and_curators(self):
        self.driver.get(f"{self.host}/community/")
        self.driver.find_element(By.ID, "openCreateCommunityBtn").click()
        time.sleep(0.5)
        self.driver.find_element(By.NAME, "name").send_keys("Comunidad de Prueba")
        time.sleep(0.5)
        self.driver.find_element(By.ID, "visual_identity_input").send_keys(
            "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSs5fQozo8bNATnNVZRQLqMOXzlTVZuagNF6A&s"
        )
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, "textarea[name='description']").send_keys("Comunidad de Prueba")
        time.sleep(0.5)
        self.driver.find_element(By.ID, "submitCreateCommunityBtn").click()
        time.sleep(1)

        self.driver.find_element(By.ID, "openCreateCommunityBtn").click()
        time.sleep(0.5)
        self.driver.find_element(By.NAME, "name").send_keys("Comunidad de Prueba 2")
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, "textarea[name='description']").send_keys(
            "Comunidad sin IDentidad Visual"
        )
        time.sleep(0.5)
        self.driver.find_element(By.ID, "submitCreateCommunityBtn").click()
        time.sleep(1)

        self.driver.find_element(By.ID, "openCreateCommunityBtn").click()
        time.sleep(0.5)
        self.driver.find_element(By.NAME, "name").send_keys("Comunidad de Prueba")
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, "textarea[name='description']").send_keys(
            "Comunidad con nombre duplicado-> ERROR"
        )
        time.sleep(0.5)
        self.driver.find_element(By.ID, "submitCreateCommunityBtn").click()
        time.sleep(1)

        self.driver.find_element(By.CSS_SELECTOR, ".card-body:nth-child(2) form > .btn").click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, ".card-body:nth-child(2) form > .btn").click()
        time.sleep(0.5)

        self.driver.find_element(By.LINK_TEXT, "My datasets").click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, ".card:nth-child(1) button[data-bs-toggle='dropdown']").click()
        time.sleep(0.5)
        self.driver.find_element(By.XPATH, "//button[normalize-space()='Comunidad de Prueba']").click()
        time.sleep(1)

        self.driver.find_element(By.LINK_TEXT, "Communities").click()
        time.sleep(0.5)
        self.driver.find_element(
            By.XPATH, "//div[h5[contains(text(),'Comunidad de Prueba')]]//a[contains(text(),'Requests')]"
        ).click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, ".modal-content .btn-group .btn-success").click()
        time.sleep(1)

        self.driver.find_element(By.CSS_SELECTOR, ".card-body:nth-child(2) form > .btn").click()
        time.sleep(0.5)

        self.driver.find_element(
            By.XPATH, "//div[h5[contains(text(),'Comunidad de Prueba')]]//a[contains(text(),'Requests')]"
        ).click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, ".modal-content .btn-group .btn-success").click()
        time.sleep(1)

        self.driver.find_element(By.LINK_TEXT, "Details").click()
        time.sleep(0.5)

        delete_btn = self.driver.find_element(
            By.CSS_SELECTOR, ".modal-body form button.btn-outline-danger[type='submit']"
        )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", delete_btn)
        time.sleep(0.2)
        delete_btn.click()
        time.sleep(1)

        self.driver.get(f"{self.host}/community/")
        time.sleep(1)

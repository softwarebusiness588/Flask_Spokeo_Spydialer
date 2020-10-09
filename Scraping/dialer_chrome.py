import argparse
import csv

import pandas as pd

from selenium import webdriver
# from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

from sqlalchemy import create_engine, String, Column, Integer, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from time import sleep

# display = Display(visible=0, size=(1920, 1080))
# display.start()
Base = declarative_base()

class PhoneNumber(Base):
    __tablename__ = 'phonenumber'
    phonenumber = Column(String, primary_key=True)
    fullname = Column(String, nullable=False)

    def __repr__(self):
        return f'<PhoneNumber(phonenumber={self.phonenumber}, name={self.fullname})>'

class DialerScraper:
    def __init__(self, kwargs):
        config = {'db_schema': 'sqlite:///spydialer.db'}
        for key, val in kwargs.items():
            if val is not None:
                config[key] = val
        self.db_engine = create_engine(config['db_schema'])
        self.db = sessionmaker(bind=self.db_engine)()
        Base.metadata.create_all(self.db_engine)

        options = webdriver.ChromeOptions()
        prefs = {"profile.managed_default_content_settings.images": 2}
        
        # options.add_argument("--headless")
        # options.add_argument("window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("start-maximized")
        options.add_argument("enable-automation")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        # options.add_argument("--single-process")
        # options.add_argument("--remote-debugging-port=9222")
        # self.driver = webdriver.Chrome(executable_path="/home/ubuntu/chromedriver", chrome_options=options)
        # chromedriver_path = os.path.join(app.instance_path, 'chromedriver')
        print("os------------", os.name)
        if(os.name == "nt"):
            self.driver = webdriver.Chrome(executable_path=r"chromedriver\chromedriver", chrome_options=options)
        else:
            self.driver = webdriver.Chrome(executable_path="chromedriver/chromedriver", chrome_options=options)
        self.config = config

    def run(self, phone):
        # results = list()
        self.driver.maximize_window()
        person = self.db.query(PhoneNumber).filter_by(phonenumber=phone).first()
        if person is None:
            try:
                self.driver.get('https://www.spydialer.com/')
                # find input and fill it with phone number
                el = self.driver.find_element_by_id('SearchInputTextBox')
                el.send_keys(phone)
                sleep(1)
                el = self.driver.find_element_by_id('ctl00_ContentPlaceHolder1_SearchImageButton')
                el.click()
                # wait for button and click
                WebDriverWait(self.driver, 30).until(
                    ec.visibility_of_element_located((By.ID, 'search-button'))
                ).click()
                WebDriverWait(self.driver, 60).until(
                    ec.visibility_of_element_located((By.ID, 'HideWaitTopDiv'))
                )
                # wait for result
                el = WebDriverWait(self.driver, 20).until(
                    ec.visibility_of_element_located((By.CLASS_NAME, 'LargeName')))
                tempPhone = PhoneNumber(phonenumber=phone, fullname=el.text)
                self.db.add(tempPhone)
                self.db.commit()
                return el.text
            except Exception as ex:
                self.driver.get_screenshot_as_file(f'{phone}.png')
                return "Could not find"
        else:
            return person.fullname
        # with open(self.config['output'], 'w', newline='') as f:
        #     writer = csv.writer(f)
        #     writer.writerows(results)

    def __del__(self):
        try:
            self.driver.quit()
            self.db.close()
        except:
            pass


def main():
    argparser = argparse.ArgumentParser(description='Dialer names scraper')
    argparser.add_argument('input', help='csv file with phones')
    argparser.add_argument('output', help='path to output csv file')
    argparser.add_argument('--headless', action='store_true', help='run webdriver in normal mode')
    argparser.add_argument('--proxy', '-p', nargs='?', help='proxy ip:port without validation')
    args = argparser.parse_args()
    scraper = DialerScraper(**args.__dict__)
    scraper.run()
    del scraper


if __name__ == '__main__':
    main()

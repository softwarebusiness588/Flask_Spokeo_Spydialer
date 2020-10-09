import argparse
import csv
import time
from time import sleep

import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

from sqlalchemy import create_engine, String, Column, Integer, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

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
        print("parameters ", kwargs)
        # df = pd.read_csv(phones_csv, index_col=False)
        # config['phones'] = map(str, df['Phone'].tolist())
        self.db_engine = create_engine(config['db_schema'])
        self.db = sessionmaker(bind=self.db_engine)()
        Base.metadata.create_all(self.db_engine)

        for key, val in kwargs.items():
            if val is not None:
                config[key] = val

        self.driver = webdriver.PhantomJS()
        self.driver.set_window_size(1024, 768)  # optional
        self.config = config

    def run(self, phone):
        # results = list()
        # for phone in self.config['phones']:
        person = self.db.query(PhoneNumber).filter_by(phonenumber=phone).first()
        if person is None:
            try:
                self.driver.get('https://www.spydialer.com/')
                # find input and fill it with phone number
                el = self.driver.find_element_by_id('SearchInputTextBox')
                el.send_keys(phone)
                sleep(.1)
                el = self.driver.find_element_by_id('ctl00_ContentPlaceHolder1_SearchImageButton')
                el.click()
                # wait for button and click
                WebDriverWait(self.driver, 60).until(
                    ec.visibility_of_element_located((By.ID, 'search-button'))
                ).click()
                # wait for result
                el = WebDriverWait(self.driver, 60).until(
                    ec.visibility_of_element_located((By.CLASS_NAME, 'LargeName')))
                
                tempPhone = PhoneNumber(phonenumber=phone, fullname=el.text)
                self.db.add(tempPhone)
                self.db.commit()
                return el.text
                
            except Exception as ex:
                self.driver.save_screenshot(f'{phone}.png')
                return "Error Could not find the name"
        else:
            return person.fullname

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
    params = {'headless': True, 'proxy': None}
    scraper = DialerScraper(params)
    scraper.run()
    del scraper


if __name__ == '__main__':
    main()

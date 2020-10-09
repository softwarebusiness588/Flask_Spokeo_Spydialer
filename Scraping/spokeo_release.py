import argparse
import csv

import pandas as pd
import json
import pickle
from urllib.parse import urljoin

import requests
import lxml.html
from sqlalchemy import create_engine, String, Column, Integer, ForeignKey, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
# from .dialer_server import DialerScraper
from .dialer_chrome import DialerScraper
import xlsxwriter

Base = declarative_base()


# database used as backup for data so you don't need start scraping from beginning
# but if you want you can use option --update
class Person(Base):
    """

    """
    __tablename__ = 'person'

    spokeo_id = Column(String, primary_key=True)
    fullname = Column(String, nullable=False)
    link = Column(String, nullable=False)
    contact = relationship('Contact')

    def __repr__(self):
        return f'<Person(name={self.fullname}, id={self.spokeo_id})>'


class Contact(Base):
    __tablename__ = 'contact'
    #
    id = Column(Integer, primary_key=True)
    contact_type = Column(String, nullable=False)
    contact = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey('person.spokeo_id'))

    # custom representation to string
    def __repr__(self):
        return f'<Contact({self.contact_type}={self.contact_type})>'


class SpokeoScraper:
    def __init__(self, kwargs):
        # todo add this in config file implemetation
        config = {
            'login': 'brightstar217118@gmail.com',
            'password': 'Notouch217',
            'db_schema': 'sqlite:///spokeo.db',
        }
        # config = configparser.ConfigParser()
        # config.read(kwargs.get('config'))
        names_csv = kwargs.pop('input')
        df = pd.read_csv(names_csv, index_col=False)
        config['names'] = df['Full Name'].tolist()
        for key, val in kwargs.items():
            if val is not None:
                config[key] = val
        self.db_engine = create_engine(config['db_schema'])
        self.db = sessionmaker(bind=self.db_engine)()
        Base.metadata.create_all(self.db_engine)

        self.s = requests.Session()
        # without replaced headers requests dropped by antibot system
        self.s.headers = {'User-Agent': 'Firefox 5.0/lol', 'Accept-Language': 'en'}
        if config.get('proxy') is not None:
            self.s.proxies = {
                'http': 'http://' + config['proxy'],
                'https': 'http://' + config['proxy'],
            }
        self.config = config
        
        #initialize dialer class
        dial_params = {'headless': True, 'proxy': None}
        dial_scraper = DialerScraper(dial_params)
        self.dial_scraper = dial_scraper

    def login(self):
        """
        Function to login on spokeo. Raise error if something wrong
        :return:
        """
        # load login page and get csrf token
        try:
            with open('cookies', 'rb') as f:
                self.s.cookies.update(pickle.load(f))
        except FileNotFoundError:
            pass
        r = self.s.get('https://www.spokeo.com/login')
        if r.status_code == 200:
            # that mean cookies works and we was redirected
            if 'login' not in r.url:
                return
            tree = lxml.html.fromstring(r.text)
            csrf_param = tree.xpath('//meta[@name="csrf-param"]/@content')[0]
            csrf_token = tree.xpath('//meta[@name="csrf-token"]/@content')[0]
            login_data = {
                csrf_param: csrf_token,
                'email': self.config['login'],
                'password': self.config['password'],
            }
            # send login data to server
            r = self.s.post('https://www.spokeo.com/sessions', data=login_data)
            if r.status_code != 200:
                raise Exception('Status code not allowed')
            elif 'error' in r.text:
                raise Exception(r.text)
            self.save_cookies()

    def run(self):
        ids = list()
        number_names = len(self.config['names'])
        max_count = self.config['max_count']
        
        for idx in range(number_names):
            name = self.config['names'][idx]
            r = self.s.get('https://www.spokeo.com/search?q=%s' % name)
            self.save_cookies()
            logs = "spokeo start processing ---> " + name
            yield [max_count*idx, number_names*max_count, 0, number_names*max_count, logs]
            logs = ""
            if r.status_code == 200:
                iteration = True
                items_count = 0
                max_page_count = self.config['max_page_count']
                page_count = 0
                while iteration:
                    page_doc = lxml.html.fromstring(r.text)
                    items = page_doc.xpath('//div[@class="single-column-list"]/a/@href')
                    if len(items) == 0:
                        break
                    for index in range(len(items)):
                        item = items[index]
                        link = urljoin(r.url, item)
                        spokeo_id = item.split('p')[-1]
                        ids.append(spokeo_id)
                        logs = "spokeo found person ---->" + str(spokeo_id)
                        person = self.db.query(Person).filter_by(spokeo_id=spokeo_id).first()
                        if person is None or self.config['update']:
                            r = self.s.get(link)
                            self.save_cookies()
                            person_doc = lxml.html.fromstring(r.text)
                            xpath = '//div[contains(@data-react-class, "UltimateProfile")]/@data-react-props'
                            summary = person_doc.xpath(xpath)
                            if len(summary) == 0:
                                ('can\'t find data', link)
                                continue
                            json_data = json.loads(summary[0])
                            person = Person(spokeo_id=spokeo_id, fullname=json_data['profile']['full_name'], link=link)
                            self.db.add(person)
                            for email in json_data['contact'].get('emails', list()):
                                try:
                                    contact = Contact(
                                        contact_type='email',
                                        contact=email['email_address'],
                                        parent_id=spokeo_id
                                    )
                                    self.db.add(contact)
                                except Exception as ex:
                                    pass
                            for phone in json_data['contact'].get('phones', list()):
                                try:
                                    contact = Contact(
                                        contact_type='phone',
                                        contact=phone['number'],
                                        parent_id=spokeo_id
                                    )
                                    self.db.add(contact)
                                except Exception as ex:
                                    pass
                            self.db.commit()
                        items_count += 1
                        yield [max_count*idx + index, number_names*max_count, 0, number_names*max_count, logs]
                        logs = ""

                        if self.config['max_count'] != 0 and items_count >= self.config['max_count']:
                            iteration = False
                            break
                    if max_page_count != 0 and page_count >= max_page_count:
                        break
                    next_page = page_doc.xpath('//a[@rel="next"]/@href')
                    if len(next_page) > 0:
                        r = self.s.get(urljoin(r.url, next_page[0]))
                    else:
                        iteration = False
        logs = "**************start scanning spydialer**********************"
        yield [number_names*max_count, number_names*max_count, 0, number_names*max_count, logs]
        logs = ""
        # Create a workbook and add a worksheet.
        workbook = xlsxwriter.Workbook('./Download/Output.xlsx')
        worksheet = workbook.add_worksheet()
        worksheet.write(0, 0, "Full Name")
        worksheet.write(0, 1, "Matching Numbers")
        worksheet.write(0, 2, "Phone Numbers")
        worksheet.write(0, 3, "Emails")
        count_match = 0
        with open(self.config['output'], 'w', newline='') as f:
            # writer = csv.writer(f)
            for person_index in range(len(ids)):
                person_id = ids[person_index]
                person = self.db.query(Person).filter_by(spokeo_id=person_id).first()
                contacts = self.db.query(Contact).filter_by(parent_id=person_id).filter_by(contact_type='phone').all()
                contacts_email = self.db.query(Contact).filter_by(parent_id=person_id).filter_by(contact_type='email').all()
                # row = [person.fullname, [c.contact for c in contacts[:4]]]
                phone_contacts = [c.contact for c in contacts[:4]]
                email_contacts = [c.contact for c in contacts_email[:4]]
                logs = str(person.fullname) + ": " + str(phone_contacts)
                yield[100, 100, person_index, len(ids), logs]
                logs = ""
                match_numbers = list()
                for phone_idx in range(len(phone_contacts)):
                    temp_progress = 1.0/len(phone_contacts)
                    logs = logs + "spydialer scanning the number " + str(phone_contacts[phone_idx])
                    yield[100, 100, person_index + temp_progress*phone_idx, len(ids), logs]
                    logs = ""
                    dial_res = self.dial_scraper.run(phone_contacts[phone_idx])
                    logs = "result for spydialer " + dial_res + "\n\n"
                    if self.compare_names(person.fullname, dial_res):
                        match_numbers.append(phone_contacts[phone_idx])
                if(len(match_numbers) > 0):
                    count_match += 1
                    worksheet.write(count_match, 0, person.fullname)
                    worksheet.write(count_match, 1, str(match_numbers))
                    worksheet.write(count_match, 2, str(phone_contacts))
                    worksheet.write(count_match, 3, str(email_contacts))
                # writer.writerow(row)
        yield [100, 100, 100, 100, "*****************completed***********"]
        workbook.close()
        # self.db.close()
        return ids
    def get_one_person(self, person_id):
        person = self.db.query(Person).filter_by(spokeo_id=person_id).first()
        contacts = self.db.query(Contact).filter_by(parent_id=person_id).all()
        return [person.fullname, [c.contact for c in contacts]]

    def compare_names(self, spokeo_name, spydialer_name):
        spokeo_name = spokeo_name.lower()
        spydialer_name = spydialer_name.lower()
        
        name_parts = spydialer_name.split()
        for part_name in name_parts:
            if part_name not in spokeo_name:
                return False
        return True

    def save_cookies(self, filename='cookies'):
        with open(filename, 'wb') as f:
            pickle.dump(self.s.cookies, f)

    def __del__(self):
        self.db.close()


def main():
    argparser = argparse.ArgumentParser(description='Spokeo contacts scraper')
    argparser.add_argument('input', help='csv file with names')
    argparser.add_argument('output', help='path to output csv file')
    argparser.add_argument('--max_count', '-m', type=int, default=3,
                           help='max count of scraped person for each name')
    argparser.add_argument('--max_page_count', '-M', type=int, default=0,
                           help='max count of page of scraped person for each name')
    argparser.add_argument('--config', '-c', default='config.ini', help='path to config file')
    argparser.add_argument('--update', '-u', action='store_true', help='update parsed data in DB if exists')
    argparser.add_argument('--proxy', '-p', nargs='?', help='proxy ip:port without validation')
    args = argparser.parse_args()
    # scraper = SpokeoScraper(**args.__dict__)
    params = {'input': 'input.csv', 'output': 'output.csv', 'max_count': 3, 'max_page_count': 0, 'config': 'config.ini', 'update': False, 'proxy': None}
    scraper = SpokeoScraper(params)
    scraper.login()
    scraper.run()
    del scraper


if __name__ == '__main__':
    main()

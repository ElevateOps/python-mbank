# -*- coding:utf8 -*-
# Pobieranie aktualnej (z ostatniego miesiaca) historii transakcji.
#
# Wymagane biblioteki: mechanize, clientform
#
# Sposob uzycia:
#
# mbank = Mbank('identyfikator', 'haslo', '71 1140 2004 0000 3902 6269 9864')
# print mbank.get_history()

import sys
import re
import mechanize
import datetime
from mechanize import Browser

DEBUG = False

# regex do wyciagania danych z history CSV
reg = re.compile('(?P<operation_date>^\d+\-\d+\-\d+);' 
                 '(?P<book_date>\d+\-\d+\-\d+);' 
                 '(?P<type>[^;]+);' 
                 '(?P<who>[^;]+);'
                 '\'(?P<account>[^;]+)\';'
                 '(?P<title>[^;]+)";'
                 '(?P<amount>[-\ 0-9,]+);' \
                 '(?P<account_balance>[-\ 0-9,]+);')

class Mbank(object):
    """
    Glowna klasa realizujaca akcje logowania, przejscia na odpowiedni
    formularz i wykonywania pozadanych akcji na stronach panelu klienta
    mbanku.
    """
    def __init__(self, id, password, bank_number=None):
        self.id = id
        self.password = password
        self.bank_number = bank_number.replace(' ', '')
        self.url = 'https://www.mbank.com.pl'
        self.form_name = 'MainForm'

        self.br = Browser()
        # Ustawienie naglowkow (szczegolnie istotny Accept-Encoding)
        # bez ktorego nie pobraloby dane w postaci CSV/HTML.
        self.br.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (X11; U; Linux x86_64; ' \
             'pl-PL; rv:1.9.2.6) Gecko/20100628 Ubuntu/10.04 ' \
             '(lucid) Firefox/3.6.6'),
            ('Accept-Encoding', 'gzip,deflate')
        ]

        # debugi
        if DEBUG:
            self.br.set_debug_redirects(True)
            self.br.set_debug_responses(True)
            self.br.set_debug_http(True)

    def login(self):
        """
        Metoda realizujaca logowanie sie do panelu klienta mbanku.
        """
        now = datetime.datetime.now()
        formated_now = now.strftime('%a, %d %b %Y, %X').lower()
        self.br.open(self.url)
        self.br.select_form(name=self.form_name)
        self.br.form.set_all_readonly(False)
        self.br.form.set_value(name='customer', value=self.id)
        self.br.form.set_value(name='password', value=self.password)
        self.br.form.set_value(name='localDT', value=formated_now)
        return self.br.submit()

    def select_account(self, bank_number):
        """
        Wybiera konto bankowe na podstawie @bank_number i wysyla POST
        z odpowiednimi parametrami dla danego konta.
        """
        self.br.open('https://www.mbank.com.pl/accounts_list.aspx')

        for l in self.br.links():
            if l.text.replace(' ', '').find(bank_number) > -1:
                break

        # Znajdz atrybut onclick dla taga <a> z numerem konta bankowego.
        for a in l.attrs:
            if a[0] == 'onclick':
                onclick = a[1].split("'")
                break

        # Wszystkie ponizsze dane pobierane sa z atrybutu onclick,
        # w ktorym to uruchamiana jest funkcja JS doSubmit().

        # Adres gdzie bedziemy slac dane.
        addr = onclick[1]
        # Metoda wysylania (POST)
        method = onclick[5]
        # Parametry
        params = onclick[7]


        self.br.select_form(name=self.form_name)
        self.br.form.action = '%s%s' % (self.url, addr)
        self.br.form.method = method
        # Aktywuj inputa __PARAMETERS (ma ustawiony status readonly)
        self.br.form.set_all_readonly(False)
        # Przypisz parametry
        self.br.form.set_value(name='__PARAMETERS', value=params)
        return self.br.submit()

    def history_form(self):
        """
        Przejscie na formularz historii transakcji.
        """
        self.br.select_form(name=self.form_name)
        self.br.form.action = '%s%s' % (self.url, '/account_oper_list.aspx')
        self.br.form.method = 'POST'
        return self.br.submit()

    def _get_history(self, type):
        """
        Metoda ustawiajaca odpowiednie parametry na formularzu historii
        transakcji i wysylajaca go.
        """
        self.br.select_form(name=self.form_name)
        # exportuj dane
        self.br.form.find_control("export_oper_history_check").items[0].selected = True
        # ustawienie selecta z typem danych (domyslnie HTML)
        self.br.form.set_value(name='export_oper_history_format', value=[type])
        self.br.form.action = '%s%s' % (self.url, '/printout_oper_list.aspx')
        self.br.form.method = 'POST'
        response = self.br.submit()
        return response.read()

    def get_history(self, type='HTML'):
        """
        Glowna metoda uruchamiajaca w sobie przejscie na formularz
        historii transakcji (po zalogowaniu) i pobranie danych.
        """
        self.login()
        self.select_account(self.bank_number)
        self.history_form()
        return self._get_history(type)

    def parse_history_csv(self, data):
        """
        Przetworzenie danych historii transakcji w postaci CSV do
        dict().
        """
        def clean_amount(amount):
            return float(amount.replace(' ', '').replace(',', '.'))

        def fixcoding(text):
            return text.decode('windows-1250').encode('utf8').decode('utf8')

        rows = []
        for row in data.split('\n'):
            f = reg.search(row)
            if not f:
                continue
            parsed_row = reg.search(row).groupdict()
            rows.append({
                'operation_date': parsed_row['operation_date'],
                'book_date': parsed_row['book_date'],
                'type': fixcoding(parsed_row['type']),
                'who': fixcoding(parsed_row['who']),
                'account': fixcoding(parsed_row['account']),
                'title': fixcoding(parsed_row['title'].strip()),
                'amount': clean_amount(parsed_row['amount']),
                'account_balance': clean_amount(parsed_row['account_balance'])
            })
        return rows

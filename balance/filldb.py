import csv
import requests
import configparser
import krakenex
import datetime
from sqlalchemy import *
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dateutil.parser import parse as parse_date
from itertools import islice,groupby

Base = declarative_base()

config = configparser.ConfigParser()
config.read('config.ini')
bankurl = config['DEFAULT']['bankurl']
exchangeurl = config['DEFAULT']['exchangeurl']
poolurl = config['DEFAULT']['poolurl']
db_conn = config['DEFAULT']['db_conn']

class mined(Base):
    __tablename__ = 'mines'
    tid     = Column(String(70), primary_key=True)
    wallet  = Column(String(50))
    time    = Column(DateTime)
    amount  = Column(Float)
    def __init__(self, row):
        self.tid    = row[0]
        self.wallet = row[1]
        self.time   = parse_date(row[2])
        self.amount = float(row[3])
    
    def __repr__(self):
        return '<Mined %s; %s; %s; %s>' % (
            self.tid, self.wallet, self.time, self.amount
        )

    def __eq__(self, other):
        return self.tid == other.tid

class trade(Base):
    __tablename__ = 'trades'
    tid         = Column(String(50), primary_key=True)
    time        = Column(DateTime)
    amount_eth  = Column(Float)
    amount_euro = Column(Float)
    fee = Column(Float)
    def __init__(self, row):
        self.tid            = row[0]
        self.amount_eth     = float(row[1])
        self.time           = parse_date(row[2])
        self.amount_euro    = float(row[3])
        self.fee            = float(row[4])
    
    def __repr__(self):
        return '<Trade %s; %s; %s; %s; %s>' % (
            self.tid, self.amount_eth, self.time, self.amount_euro, self.fee
        )

    def __eq__(self, other):
        return self.tid == other.tid
        
class deposit(Base):
    __tablename__ = 'deposits'
    tid     = Column(String(50), primary_key=True)
    time    = Column(DateTime)
    amount  = Column(Float)
    def __init__(self, row):
        self.tid            = row[0]
        self.amount         = float(row[1])
        self.time           = parse_date(row[2])
    
    def __repr__(self):
        return '<Deposit %s; %s; %s>' % (
            self.tid, self.amount, self.time
        )

    def __eq__(self, other):
        return self.tid == other.tid

class withdrawal(Base):
    __tablename__ = 'withdrawals'
    tid     = Column(String(50), primary_key=True)
    time    = Column(DateTime)
    amount  = Column(Float)
    def __init__(self, row):
        self.tid            = row[0]
        self.amount         = float(row[1])
        self.time           = parse_date(row[2])
    
    def __repr__(self):
        return '<Withdrawal %s; %s; %s>' % (
            self.tid, self.amount, self.time
        )

    def __eq__(self, other):
        return self.tid == other.tid
        
class SEPA(Base):
    __tablename__ = 'sepas'
    tid     = Column(String(50), primary_key=True)
    time    = Column(DateTime)
    amount  = Column(Float)
    def __init__(self, row):
        self.time           = parse_date(row[1]).replace(hour=23, minute=59)
        self.tid            = row[4]
        if row[3] == "Überweisung":
            self.withdrawal = True
        else:
            self.withdrawal = False
        self.amount         = float(row[5].replace(',', '.'))
    
    def __repr__(self):
        return '<SEPA %s; %s; %s;>' % (
            self.tid, self.time, self.amount
        )

    def __eq__(self, other):
        return self.tid == other.tid
        
trades      = []
mines       = []
sepas       = []
withdrawals = []
deposits    = []

k = krakenex.API()
k.load_key('kraken.key')
th = k.query_private('TradesHistory', {})
for tr in th['result']['trades']:
    if th['result']['trades'][tr]['type'] == "sell" and th['result']['trades'][tr]['pair'] == "XETHZEUR":
        t =trade([  th['result']['trades'][tr]['ordertxid'],
                    th['result']['trades'][tr]['vol'],
                    datetime.datetime.fromtimestamp(th['result']['trades'][tr]['time']).strftime('%Y-%m-%d %H:%M:%S'),
                    th['result']['trades'][tr]['cost'],
                    th['result']['trades'][tr]['fee']])
        trades.append(t)
        
trades.sort(key=lambda x: x.time, reverse=False)
tmptrades = []
for key, group in groupby(trades, lambda x: x.tid):
    sum_eth  = 0
    sum_euro = 0 
    sum_fee  = 0
    time = ""
    for thing in group:
        sum_eth  += thing.amount_eth
        sum_euro += thing.amount_euro
        sum_fee  += thing.fee
        time      = thing.time
    t =trade([key,sum_eth,time.strftime('%Y-%m-%d %H:%M:%S'),sum_euro,sum_fee])
    tmptrades.append(t)
trades = tmptrades 
        
d = k.query_private('Ledgers', {'type':'withdrawal', 'asset':'ZEUR'})
for dl in d['result']['ledger']:
    t = withdrawal([d['result']['ledger'][dl]['refid'], d['result']['ledger'][dl]['amount'], datetime.datetime.fromtimestamp(d['result']['ledger'][dl]['time']).strftime('%Y-%m-%d %H:%M:%S')])
    withdrawals.append(t)
    
d = k.query_private('Ledgers', {'type':'deposit', 'asset':'XETH'})
for dl in d['result']['ledger']:
    t = deposit([d['result']['ledger'][dl]['refid'], d['result']['ledger'][dl]['amount'], datetime.datetime.fromtimestamp(d['result']['ledger'][dl]['time']).strftime('%Y-%m-%d %H:%M:%S')])
    deposits.append(t)
        
response = requests.get(poolurl)
lines = csv.reader(response.text.splitlines() , delimiter=',')
for line in lines:
    t = mined(line)
    mines.append(t)
        
response = requests.get(bankurl)
lines = csv.reader(response.text.splitlines() , delimiter=';')
for line in islice(lines, 7, None):
    t = SEPA(line)
    sepas.append(t)

result = trades + mines + sepas + withdrawals + deposits
result.sort(key=lambda x: x.time, reverse=False)



db = create_engine(db_conn)
db.echo = False 
Base.metadata.create_all(db)
Session = sessionmaker(bind=db)
session = Session()

def insert_if_new(t):
    s = tradesDB.select(tradesDB.c.tid == t.tid)
    rs = db.execute(s)
    if len(rs.fetchall()) == 0:
        print("New Record with id %s" % t.tid)
        i = tradesDB.insert()
        db.execute(statement=i,tid=t.tid, time=t.time, amount_eth=t.amount_eth, amount_euro=t.amount_euro, fee=t.fee)
    else:
        print("Record with id %s already exists" % t.tid)

for res in result:
    session.add(res)
session.commit()
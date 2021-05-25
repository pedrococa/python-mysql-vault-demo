import mysql.connector
from mysql.connector import errorcode
import datetime
import hvac
import base64
import logging
import time

customer_table_file = open('customer_table.txt', 'r')
customer_table = customer_table_file.read()
customer_table_file.close()

seed_customers_file = open('seed_customers.txt', 'r')
seed_customers = seed_customers_file.read()
seed_customers_file.close()
logger = logging.getLogger(__name__)

class DbClient:
    conn = None
    vault_client = None
    key_name = None
    mount_point = None
    username = None
    password = None
    is_initialized = False

    #def __init__(self, uri, prt, uname, pw, db):
    #    self.init_db(uri, prt, uname, pw, db)

    def init_db(self, uri, prt, uname, pw, db):
        self.uri = uri
        self.port = prt
        self.username = uname
        self.password = pw
        self.db = db
        self.connect_db(uri, prt, uname, pw)
        cursor = self.conn.cursor()
        logger.info("Preparing database {}...".format(db))
        cursor.execute('CREATE DATABASE IF NOT EXISTS `{}`'.format(db))
        cursor.execute('USE `{}`'.format(db))
        logger.info("Preparing customer table...")
        cursor.execute(customer_table)
        cursor.execute(seed_customers)
        self.conn.commit()
        cursor.close()
        self.is_initialized = True

    # Later we will check to see if this is None to see whether to use Vault or not
    def init_vault(self, addr, token, namespace, path, key_name):
        if not addr or not token:
            logger.warning('Skipping initialization...')
            return
        else:
            logger.warning("Connecting to vault server: {}".format(addr))
            self.vault_client = hvac.Client(url=addr, token=token, namespace=namespace)
            self.key_name = key_name
            self.mount_point = path
            logger.debug("Initialized vault_client: {}".format(self.vault_client))

    def vault_db_auth(self, path):
        try:
            resp = self.vault_client.read(path)
            self.username = resp['data']['username']
            self.password = resp['data']['password']
            logger.debug('Retrieved username {} and password {} from Vault.'.format(self.username, self.password))
        except Exception as e:
            logger.error('An error occurred reading DB creds from path {}.  Error: {}'.format(path, e))

    # the data must be base64ed before being passed to encrypt
    def encrypt(self, value):
        try:
            response = self.vault_client.secrets.transit.encrypt_data(
                mount_point = self.mount_point,
                name = self.key_name,
                plaintext = base64.b64encode(value.encode()).decode('ascii')
            )
            logger.debug('Response: {}'.format(response))
            return response['data']['ciphertext']
        except Exception as e:
            logger.error('There was an error encrypting the data: {}'.format(e))

    # The data returned from Transit is base64 encoded so we decode it before returning
    def decrypt(self, value):
        # support unencrypted messages on first read
        logger.debug('Decrypting {}'.format(value))
        if not value.startswith('vault:v'):
            return value
        else:
            try:
                response = self.vault_client.secrets.transit.decrypt_data(
                    mount_point = self.mount_point,
                    name = self.key_name,
                    ciphertext = value
                )
                logger.debug('Response: {}'.format(response))
                plaintext = response['data']['plaintext']
                logger.debug('Plaintext (base64 encoded): {}'.format(plaintext))
                decoded = base64.b64decode(plaintext).decode()
                logger.debug('Decoded: {}'.format(decoded))
                return decoded
            except Exception as e:
                logger.error('There was an error encrypting the data: {}'.format(e))

    # Long running apps may expire the DB connection
    def _execute_sql(self,sql,cursor):
        try:
            cursor.execute(sql)
            return 1
        except mysql.connector.errors.OperationalError as e:
            if e[0] == 2006:
                logger.error('Error encountered: {}.  Reconnecting db...'.format(e))
                self.init_db(self.uri, self.port, self.username, self.password, self.db)
                cursor = self.conn.cursor()
                cursor.execute(sql)
                return 0

    def connect_db(self, uri, prt, uname, pw):
        logger.debug('Connecting to {} with username {} and password {}'.format(uri, uname, pw))
        for i in range(0,10):
            try:
                self.conn = mysql.connector.connect(user=uname, password=pw, host=uri, port=prt)
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                    logger.error("Something is wrong with your user name or password")
                elif err.errno == errorcode.ER_BAD_DB_ERROR:
                    logger.error("Database does not exist")
                else:
                    logger.error(err)
                logger.debug("Sleeping 5 seconds before retry")
                time.sleep(5)
            

    def get_customer_records(self, num = None, raw = None):
        if num is None:
            num = 50
        statement = 'SELECT * FROM `customers` LIMIT {}'.format(num)
        cursor = self.conn.cursor()
        self._execute_sql(statement, cursor)
        results = []
        for row in cursor:
            try:
                r = {}
                r['customer_number'] = row[0]
                r['birth_date'] = row[1]
                r['first_name'] = row[2]
                r['last_name'] = row[3]
                r['create_date'] = row[4]
                r['ssn'] = row[5]
                r['ccn'] = row[6]
                r['account'] = row[7]
                r['address'] = row[8]
                if self.vault_client is not None and not raw:
                    r['birth_date'] = self.decrypt(r['birth_date'])
                    r['ssn'] = self.decrypt(r['ssn'])
                    r['ccn'] = self.decrypt(r['ccn'])
                    r['address'] = self.decrypt(r['address'])
                results.append(r)
            except Exception as e:
                logger.error('There was an error retrieving the record: {}'.format(e))
        return results

    def get_customer_record(self, id):
        statement = 'SELECT * FROM `customers` WHERE cust_no = {}'.format(id)
        cursor = self.conn.cursor()
        self._execute_sql(statement, cursor)
        results = []
        for row in cursor:
            try:
                r = {}
                r['customer_number'] = row[0]
                r['birth_date'] = row[1]
                r['first_name'] = row[2]
                r['last_name'] = row[3]
                r['create_date'] = row[4]
                r['ssn'] = row[5]
                r['ccn'] = row[6]
                r['account'] = row[7]
                r['address'] = row[8]
                if self.vault_client is not None:
                    r['birth_date'] = self.decrypt(r['birth_date'])
                    r['ssn'] = self.decrypt(r['ssn'])
                    r['ccn'] = self.decrypt(r['ccn'])
                    r['address'] = self.decrypt(r['address'])
                results.append(r)
            except Exception as e:
                logger.error('There was an error retrieving the record: {}'.format(e))
        return results

    def insert_customer_record(self, record):
        if self.vault_client is None:
            statement = '''INSERT INTO `customers` (`birth_date`, `first_name`, `last_name`, `create_date`, `social_security_number`, `credit_card_number`, `account`, `address`)
                            VALUES  ("{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}");'''.format(record['birth_date'], record['first_name'], record['last_name'], record['create_date'], record['ssn'], record['ccn'], record['account'], record['address'] )
        else:
            statement = '''INSERT INTO `customers` (`birth_date`, `first_name`, `last_name`, `create_date`, `social_security_number`, `credit_card_number`, `account`, `address`)
                            VALUES  ("{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}");'''.format(self.encrypt(record['birth_date']), record['first_name'], record['last_name'], record['create_date'], self.encrypt(record['ssn']), self.encrypt(record['ccn']), record['account'], self.encrypt(record['address']) )
        logger.debug('SQL Statement: {}'.format(statement))
        cursor = self.conn.cursor()
        self._execute_sql(statement, cursor)
        self.conn.commit()
        return self.get_customer_records()

    def update_customer_record(self, record):
        if self.vault_client is None:
            statement = '''UPDATE `customers`
                       SET birth_date = "{}", first_name = "{}", last_name = "{}", social_security_number = "{}", credit_card_number = "{}", account = "{}", address = "{}"
                       WHERE cust_no = {};'''.format(record['birth_date'], record['first_name'], record['last_name'], record['ssn'], record['ccn'], record['account'], record['address'], record['cust_no'] )
        else:
            statement = '''UPDATE `customers`
                       SET birth_date = "{}", first_name = "{}", last_name = "{}", social_security_number = "{}", credit_card_number = "{}", account = "{}", address = "{}"
                       WHERE cust_no = {};'''.format(self.encrypt(record['birth_date']), record['first_name'], record['last_name'], self.encrypt(record['ssn']), self.encrypt(record['ccn']), record['account'], self.encrypt(record['address']), record['cust_no'] )
        logger.debug('Sql Statement: {}'.format(statement))
        cursor = self.conn.cursor()
        self._execute_sql(statement, cursor)
        self.conn.commit()
        return self.get_customer_records()

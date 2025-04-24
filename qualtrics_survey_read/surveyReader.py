import requests
from requests.adapters import HTTPAdapter, Retry
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import json
import time
import pandas as pd
import os
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime, timezone
from collections import Counter
from typing_extensions import Self

class SurveyReader:
    """class capable of reading qualtrics survey files from the api, requires api key with :read_responses scope"""

    def __init__(self , pathToFile: str = None , dataCenter:str = None , clientId:str = None , clientSecret:str = None , surveyId:str = None , subDirTarget:str = None , altBaseURL:str = None , altAPIURL:str = None , altExportURL:str = None):
        
        """class that encapsulates reading from a qualtrics survey via the API. See https://api.qualtrics.com/9398592961ced-o-auth-authentication-client-credentials for how to on making credentials and note that only :read_responses scope is required for this object. See https://api.qualtrics.com/1aea264443797-base-url-and-datacenter-i-ds for finding datacenter ids.
        
        Keyword Parameters:
        -
        pathToFile (str) : The file path to read the qualtrics credentials from. Expects crediantials in JSON format adhering to the folowing schema '{"client_id" : "urID" , "client_secret" : "urSecret" , "datacenter" : "urdatacenter" , "survey_id" : "ursurveyId"}'.
        
        dataCenter (str) : you may specify the datacenter id.
        
        clientId (str) : the client id for qualtrics client.
        
        clientSecret (str) : the cleint secret for qualtrics Oauth.
        
        surveyId (str) : the id for your survey. If you do not want to specify this in a config file you can leave it out and specify it on object creation as a passed value. This is not the case with the other config params - secret, id, etc.. the survey ID is found in the url to your survey i.e. in when viewing your survey with url https://foo.yul1.qualtrics.com/survey-builder/SWECCNSJKJK!!@##/edit , the id would be 'SWECCNSJKJK!!@##' (this isnt a real id btw)
        
        subDirTarget (str) : The directory to write the temp files created during survey decompression into a dataframe, defaults to current working directory.
        
        altBaseURL (str) : Specify an alternate base url for Auth API requests. Current default is - https://urdatacenter.qualtrics.com/oauth2/token

        altAPIURL (str) : Specify an alternate base url for API requests. Current default is - https://yourdatacenter.qualtrics.com/API

        altExportURL (str) : Specify an alternate export url path to add to the APIURL. Current default is - /v3/surveys/ursurveyID/export-responses
        """

        self.__file_creds = None
        self.__data_center = None
        self.__client_id = None
        self.__client_secret = None
        self.survey_id = None

        self.__sub_directory_targ = subDirTarget

        self.base_auth_url = None
        self.api_url = None
        self.export_url = None

        assert not (  self.__sub_directory_targ != None and not os.path.isdir(self.__sub_directory_targ)  ), f"sub directory to target: '{self.__sub_directory_targ}' does not exist"
        assert (pathToFile != None) ^ ( dataCenter != None or clientId != None or clientSecret != None ) , "config file cannot be specified if credentials are passed as parameter. You may omit surveyId form the config and pass as a param though."
        assert (pathToFile == None) ^ ( dataCenter == None or clientId == None or clientSecret == None ) , "missing required qualtrics auth parameter, all aut params must be specified at creation if pathToFile is blank."

        if(pathToFile != None):

            with open(pathToFile , 'r') as f:

                self.__file_creds = json.loads(f.read())

                self.__data_center = self.__file_creds.get('datacenter')
                self.__client_id = self.__file_creds.get('client_id')
                self.__client_secret = self.__file_creds.get('client_secret')
                self.survey_id = self.__file_creds.get('survey_id')

                if(self.survey_id == None):
                    self.survey_id = surveyId

        
        if(pathToFile == None):

            if(dataCenter == None or type(dataCenter) != str):
                raise ValueError("dataCenter is not defined or invalid type, expected type 'str'")
            elif(clientId == None or type(dataCenter) != str):
                raise ValueError("clientId is not defined or invalid type, expected type 'str'")
            elif(clientSecret == None or type(dataCenter) != str):
                raise ValueError("clientSecret is not defined or invalid type, expected type 'str'")
            elif(surveyId == None or type(dataCenter) != str):
                raise ValueError("surveyId is not defined or invalid type, expected type 'str'")
            
            self.__data_center = dataCenter
            self.__client_id = clientId
            self.__client_secret = clientSecret
            self.survey_id = surveyId


        self.api_url = f"https://{self.__data_center}.qualtrics.com/API"
        self.base_auth_url = f"https://{self.__data_center}.qualtrics.com/oauth2/token"
        self.export_url = self.api_url + f'/v3/surveys/{self.survey_id}/export-responses'

        if(altAPIURL != None and type(altAPIURL) == str):
            self.api_url = altAPIURL
        if(altBaseURL != None and type(altBaseURL) == str):
            self.base_auth_url = altBaseURL
        if(altExportURL != None and type(altExportURL) == str):
            self.export_url = altExportURL

        if(type(self.survey_id) != str or self.survey_id == None):
            raise ValueError('surveyId not speified or invalid type')


    def read(self , includeLabels:bool = True , secondsToWait:int = 60) -> Self:

        """Reads a file from qualtrics using the parameters specified and holds the compressed bytestring inside the object returns the object it is called upon for chaining
        
        Keyword Parameters:
        -
        includeLabels (bool) : whether or not to export label columns from qualtrics or only recode values.
        
        secondsToWait (int) : An int representing how long to wait for the file download to succeed before terminating with an error, default 2 minutes."""

        assert isinstance(secondsToWait , int) , f"secondsToWait is of invalid type {type(secondsToWait)}, expected 'int'"

        assert isinstance(includeLabels , bool), f"expected type variable of type 'boolean' but got type {type(includeLabels)}"

        auth_token = None

        with requests.sessions.Session() as session:

            retrys = HTTPAdapter( max_retries= Retry(total= 5 , backoff_factor=1 ,  status_forcelist= [ 429, 500, 502, 503, 504 ]) )

            session.mount('https://' , retrys)

            auth_response = session.post(self.base_auth_url , auth=(self.__client_id , self.__client_secret) , data= {'grant_type': 'client_credentials','scope': 'read:survey_responses'})

            if(auth_response.status_code != 200):
                raise ConnectionError(f"unable to aquire qualtrics auth token, server responsing with status code {auth_response.status_code} and message: {auth_response.json()}") 
            
            auth_token = auth_response.json()['access_token']

            start_export_header = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {auth_token}"
            }

            export_options = {"format" : "csv" , 'compress' : True , "includeLabelColumns" : includeLabels}

            survey_export_start_response = session.post(self.export_url , headers=start_export_header , json=export_options)

            if(survey_export_start_response.status_code != 200):
                raise ConnectionError(f"unable to start response export process, server responding with status code: {survey_export_start_response.status_code} and message: {survey_export_start_response.json()}")
            
            export_start_data = survey_export_start_response.json()
            

            with requests.sessions.Session() as export_session:

                poll_retry = HTTPAdapter ( max_retries= Retry(total=5 , backoff_factor= 1 , status_forcelist= [ 429, 500, 502, 503, 504 ]) )

                export_session.mount('https://' , poll_retry)

                survey_responses_status = export_session.get(url = self.export_url + f'/{export_start_data['result']['progressId']}' , headers= {'Authorization' : f'Bearer {auth_token}'}   )

                count = 0

                while( str(survey_responses_status.json()['result']['status'].lower()) == 'inprogress' and survey_responses_status.status_code == 200 and count < secondsToWait):

                    count += 1

                    time.sleep(2)

                    survey_responses_status = export_session.get(url= self.export_url + f'/{export_start_data['result']['progressId']}' , headers= {'Authorization' : f'Bearer {auth_token}'}  )

                
                if(count >= secondsToWait):
                    raise ConnectionAbortedError(f"file export aborted, polling for status timed out after {count} seconds")
                
                if(survey_responses_status.status_code != 200):
                    raise ConnectionError(f"survey response status polling failed with status code: {survey_responses_status.status_code} and messgae: {survey_responses_status.json()}")
                
                if(survey_responses_status.json()['result']['status'].lower() != 'complete'):
                    raise ConnectionError(f"survey response export non successful, qualtrics responding with: {survey_responses_status.json()['result']['status'].lower()} and message: {survey_responses_status.json()['result']['status']}")
                
                

                survey_file = export_session.get(url=self.export_url + f'/{survey_responses_status.json()['result']['fileId']}/file' , headers= {'Authorization' : f'Bearer {auth_token}'} )

                if(survey_file.status_code != 200):
                    raise ConnectionError(f"survey export failed with status code: {survey_file.status_code}")
                


                self._compressed_csv = survey_file.content #holds compressed bytes

                return self

    @staticmethod
    def __df_cleaner( df:pd.DataFrame = None,  dropHeaders:bool = True) -> pd.DataFrame:
    
        df.columns = [(lambda x : x[:250] if len(x) > 255 else x)(x) for x in list(df.iloc[0].values)]

        duplicate_column_check = Counter(df.columns)
        dupes = []

        for key,value in duplicate_column_check.items():
            if(value > 1 ):
                dupes.append(key)

        if(len(dupes) > 0 ):
            temp = {}

            for dupe in dupes:
                temp[dupe] = -1

            columns = []

            for column in df.columns:

                if(column in temp):
                    temp[column] = temp[column] + 1
                    column = column + ' (' + str(temp.get(column)) + ')'
                    

                columns.append(column)

            df.columns = columns

        if(dropHeaders):
            df = df.drop(index=[0,1]) #drops extra headers qualtrics sends

        df = df.reset_index(drop=True)
    
        return df
    
    def to_df(self , dropHeaders:bool = True , keepFile:bool = False) -> dict:

        """turns a compressed bytestring held in a surveyReader object into a pandas dataframe and returns the df(s) as items in a dictionary with the survey name as the key.
        
        Keyword Parameters:
        -
        dropHeaders (bool) : whether to drop the extra headers qualtrics typically sends. If true will drop the first and second rows of the df.
        
        keepFile (bool) : Whether to keep the csv file created when the bytestring is decompressed. File will be written to the current working directory if 'subDirTarget' was not specified on object creation."""

        assert isinstance(keepFile , bool), "keepFile is not boolean"
        assert isinstance(dropHeaders, bool) , "dropHeaders is not boolean"

        if( not hasattr(self , '_compressed_csv') ):
            raise NameError("btye array not found, did you successfully run .read() first?")
        
        with BytesIO(self._compressed_csv) as zipped: #psuedo in memory file

            with ZipFile(zipped , 'r') as file:

                self._nameslist = file.namelist()

                if(self.__sub_directory_targ != None):
                    file.extractall(self.__sub_directory_targ)
                else:
                    file.extractall(os.getcwd())

                self._dfs = []

                for name in self._nameslist:

                    df = pd.read_csv(name)

                    df = self.__df_cleaner( df , dropHeaders)

                    self._dfs.append(df)

                    if(not keepFile):
                        os.remove(name)

        
        zipped = zip( self._nameslist , self._dfs )

        return dict(zipped)

 
def read_sql(cur:snowflake.connector.cursor , sql:str ) -> pd.DataFrame:
    """Executes any arbitrary sql using the snowflake cursor object passes and the sql passed as a string. returns a pandas dataframe.
    
    Keyword Parameters:
    -
    cur (snowflake.connector.cursor) : the snowflake cursor object to use.
    
    sql (str) : the string containing the sql you wish to execute"""

    assert isinstance(cur , snowflake.connector.cursor) , f"parameter 'cur' is of type: {type(cur)} , expected snowflake.connector.cursor"
    assert isinstance(sql , str) , f"parameter 'sql' is of type: {type(sql)} , expected str"

    cur.execute(sql)

    df = pd.concat(cur.fetch_pandas_batches()) # Makes a df out of all results

    df.columns = [col.lower() for col in df.columns] # Makes column headers lowercase.

    df = df.reset_index(drop=True)

    return df

def to_snowflake(conn:snowflake.connector, df:pd.DataFrame , tableName:str = None,  overwrite:bool = False , createTable:bool = False , onlyPushNew:bool = False , snowflakeIdColumn:str = None , dfIdColumn:str = None) -> int:

    """writes a pd.dataframe to the snowflake schema specied in the passed connection, with the tablename given. set overwrite and autocreate to true to truncate an existing table and recreate. Set overwrite to true and autocreate to false to truncate and repopulate. If onlyPushNew is set to True, you MUST specify the id columns to decide what is new from the snowflake table AND from the passed dataframe - these will be compared to see what rows have/havent been pushed to snowflake yet.
    
    Keyword Parameters:
    -
    conn (str) : the snowflake connection you want to use, be sure to specify a target schema when you create it.

    df (pd.Dataframe) : the dataframe you want to migrate to snowflake.

    overwrite (bool) : whether or not to overwrite (truncate) an existing table.

    createTable (bool) : whether or not to create a table if it does not exist, if set to True with overwrite - will drop and recreate target table.

    onlyPushNew (bool) : whether to only push new content based on a set of id columns to snowflake. If set to true you MUST specify snowflake id and df id columns.

    snowflakeIdColumn (str) : the column name for the table in snowflake to use as the comparison when deciding if a row is new or not.

    dfIdColumn (str) : the column name for the column you want to use as the id column in the passed dataframe. Will be used to compare with snowflake id column to determine which rows are new and should be pushed."""

    assert isinstance(overwrite , bool) , f'overwrite is invalid type, {type(overwrite)}, expected bool'
    assert isinstance(createTable , bool) , f'createTable is invalid type, {type(createTable)}, expected bool'
    assert isinstance(onlyPushNew , bool) , f'onlypushnew is invalid type, {type(onlyPushNew)}, expected bool'
    assert isinstance(tableName , str), f"tableName is of type {type(tableName)} , expected str. tableName is the name of the table you want to write to / create"
    assert isinstance(df , pd.DataFrame) , f"df is of type {type(df)} , expected pandas dataframe"
    assert isinstance(conn , snowflake.connector.connection) , f"conn is of type {type(conn)} , expected snowflake.connector.connection"

    if(onlyPushNew and (type(snowflakeIdColumn) != str or type(dfIdColumn) != str )):
        raise ValueError(f'onlyPushNew or specified but idcolumn params is invalid type of {type(snowflakeIdColumn)} , {type(dfIdColumn)} - expected str')
    
    try:
        cur = conn.cursor()
    except:
        raise ConnectionError("passed connection object does not have a valid .cursor() method. Did you pass an active snowflake.connector connection?")
    


    if(onlyPushNew):

        try:
            already_written = list(read_sql(cur,f'select \"{snowflakeIdColumn}\" from {tableName}')[snowflakeIdColumn.lower()].astype(str))
        except ValueError:
            already_written = []

        if(not len(already_written) == 0):       

            to_write = list(df[dfIdColumn].astype(str))

            to_drop = [True if x not in already_written else False for x in to_write]

            df = df[to_drop]

            if(df.empty):
                return len(df)

        now = datetime.now(timezone.utc)

        df['upload_occured_on'] = pd.to_datetime(now)


        write_pandas(conn=conn , df=df , table_name=tableName , auto_create_table=createTable , overwrite=overwrite , use_logical_type=True)

        return len(df)
    
    else:
        now = datetime.now(timezone.utc)

        df['upload_occured_on'] = pd.to_datetime(now)

        write_pandas(conn=conn , df=df , table_name=tableName , auto_create_table=createTable , overwrite=overwrite , use_logical_type=True)

        return len(df)

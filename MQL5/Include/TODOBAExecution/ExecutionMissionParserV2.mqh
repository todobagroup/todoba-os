#ifndef TODOBA_EXECUTION_MISSION_PARSER_V2_MQH
#define TODOBA_EXECUTION_MISSION_PARSER_V2_MQH


#include <TODOBAExecution/ExecutionMissionParser.mqh>


class TODOBAExecutionMissionParserV2
{
private:

   static bool ExtractPositiveLong(
      const string json,
      const string key,
      long &value
   )
   {
      string marker =
         "\""
         + key
         + "\":";

      int start = StringFind(
         json,
         marker
      );

      if(start < 0)
         return false;

      start += StringLen(
         marker
      );

      int finish = start;

      while(finish < StringLen(json))
      {
         ushort character =
            StringGetCharacter(
               json,
               finish
            );

         if(
            character == ',' ||
            character == '}'
         )
         {
            break;
         }

         if(
            character < '0' ||
            character > '9'
         )
         {
            return false;
         }

         finish++;
      }

      if(finish <= start)
         return false;

      string raw = StringSubstr(
         json,
         start,
         finish - start
      );

      value = StringToInteger(
         raw
      );

      return value > 0;
   }


public:

   static bool Parse(
      const string response,
      TODOBAExecutionMission &mission
   )
   {
      if(
         !TODOBAExecutionMissionParser::Parse(
            response,
            mission
         )
      )
      {
         return false;
      }

      if(
         !ExtractPositiveLong(
            response,
            "security_sequence",
            mission.security_sequence
         )
      )
      {
         return false;
      }

      return true;
   }


   static bool ExtractSignature(
      const string response,
      string &signature
   )
   {
      return (
         TODOBAExecutionMissionParser::ExtractSignature(
            response,
            signature
         )
      );
   }
};


#endif
#ifndef TODOBA_EXECUTION_MISSION_PARSER_MQH
#define TODOBA_EXECUTION_MISSION_PARSER_MQH


struct TODOBAExecutionMission
{
   string mission_id;
   string agent_id;
   string account_fingerprint;
   string symbol;
   string order_type;

   double volume;
   double entry;
   bool has_entry;

   double sl;
   double tp;

   long magic_number;
   string comment;

   string created_at;
   string expires_at;

   long sequence;
};


class TODOBAExecutionMissionParser
{
private:

   static bool ExtractString(
      const string json,
      const string key,
      string &value
   )
   {
      string marker =
         "\""
         + key
         + "\":\"";

      int start = StringFind(
         json,
         marker
      );

      if(start < 0)
         return false;

      start += StringLen(
         marker
      );

      int finish = StringFind(
         json,
         "\"",
         start
      );

      if(finish < 0)
         return false;

      value = StringSubstr(
         json,
         start,
         finish - start
      );

      return true;
   }


   static bool ExtractNumber(
      const string json,
      const string key,
      double &value
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

         finish++;
      }

      if(finish <= start)
         return false;

      string raw = StringSubstr(
         json,
         start,
         finish - start
      );

      value = StringToDouble(
         raw
      );

      return true;
   }


   static bool ExtractLong(
      const string json,
      const string key,
      long &value
   )
   {
      double number = 0.0;

      if(
         !ExtractNumber(
            json,
            key,
            number
         )
      )
      {
         return false;
      }

      value = (long)number;

      return true;
   }


public:

   static bool Parse(
      const string response,
      TODOBAExecutionMission &mission
   )
   {
      if(
         StringFind(
            response,
            "\"status\":\"available\""
         ) < 0
      )
      {
         return false;
      }

      if(
         !ExtractString(
            response,
            "mission_id",
            mission.mission_id
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "agent_id",
            mission.agent_id
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "account_fingerprint",
            mission.account_fingerprint
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "symbol",
            mission.symbol
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "order_type",
            mission.order_type
         )
      )
         return false;

      if(
         !ExtractNumber(
            response,
            "volume",
            mission.volume
         )
      )
         return false;

      string entry_marker =
         "\"entry\":null";

      if(
         StringFind(
            response,
            entry_marker
         ) >= 0
      )
      {
         mission.entry = 0.0;
         mission.has_entry = false;
      }
      else
      {
         if(
            !ExtractNumber(
               response,
               "entry",
               mission.entry
            )
         )
            return false;

         mission.has_entry = true;
      }

      if(
         !ExtractNumber(
            response,
            "sl",
            mission.sl
         )
      )
         return false;

      if(
         !ExtractNumber(
            response,
            "tp",
            mission.tp
         )
      )
         return false;

      if(
         !ExtractLong(
            response,
            "magic_number",
            mission.magic_number
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "comment",
            mission.comment
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "created_at",
            mission.created_at
         )
      )
         return false;

      if(
         !ExtractString(
            response,
            "expires_at",
            mission.expires_at
         )
      )
         return false;

      if(
         !ExtractLong(
            response,
            "sequence",
            mission.sequence
         )
      )
         return false;

      return true;
   }


   static bool ExtractSignature(
      const string response,
      string &signature
   )
   {
      return ExtractString(
         response,
         "mission_signature",
         signature
      );
   }
};


#endif
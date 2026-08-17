#ifndef TODOBA_CONTROL_MISSION_PARSER_MQH
#define TODOBA_CONTROL_MISSION_PARSER_MQH


struct TODOBAControlMission
{
   string mission_id;
   string agent_id;
   string account_fingerprint;

   string action;
   string symbol;

   long magic_number;
   long requested_by_sender_id;

   string created_at;
   string expires_at;

   long sequence;
};


class TODOBAControlMissionParser
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


   static bool ExtractLong(
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

         finish++;
      }

      if(finish <= start)
         return false;

      string raw = StringSubstr(
         json,
         start,
         finish - start
      );

      if(StringLen(raw) == 0)
         return false;

      value = StringToInteger(
         raw
      );

      return true;
   }


public:

   static bool Parse(
      const string response,
      TODOBAControlMission &mission
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
            "action",
            mission.action
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
         !ExtractLong(
            response,
            "magic_number",
            mission.magic_number
         )
      )
         return false;

      if(
         !ExtractLong(
            response,
            "requested_by_sender_id",
            mission.requested_by_sender_id
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
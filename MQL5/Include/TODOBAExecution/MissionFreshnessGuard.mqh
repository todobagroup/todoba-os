#ifndef TODOBA_MISSION_FRESHNESS_GUARD_MQH
#define TODOBA_MISSION_FRESHNESS_GUARD_MQH


class TODOBAMissionFreshnessGuard
{
public:

   static bool Validate(
      const string created_at_text,
      const string expires_at_text
   )
   {
      datetime created_at = 0;
      datetime expires_at = 0;

      if(
         !ParseUtcIso8601(
            created_at_text,
            created_at
         )
      )
      {
         return false;
      }

      if(
         !ParseUtcIso8601(
            expires_at_text,
            expires_at
         )
      )
      {
         return false;
      }

      if(expires_at <= created_at)
         return false;

      datetime now =
         TimeGMT();

      if(expires_at <= now)
         return false;

      return true;
   }


private:

   static bool ParseUtcIso8601(
      const string value,
      datetime &result
   )
   {
      result = 0;

      int length =
         StringLen(value);

      if(length < 20)
         return false;

      if(StringSubstr(value, 4, 1) != "-")
         return false;

      if(StringSubstr(value, 7, 1) != "-")
         return false;

      if(StringSubstr(value, 10, 1) != "T")
         return false;

      if(StringSubstr(value, 13, 1) != ":")
         return false;

      if(StringSubstr(value, 16, 1) != ":")
         return false;

      if(StringSubstr(value, length - 1, 1) != "Z")
         return false;


      string fractional_part = "";

      if(length > 20)
      {
         if(StringSubstr(value, 19, 1) != ".")
            return false;

         fractional_part =
            StringSubstr(
               value,
               20,
               length - 21
            );

         if(StringLen(fractional_part) == 0)
            return false;

         for(
            int index = 0;
            index < StringLen(fractional_part);
            index++
         )
         {
            ushort character =
               StringGetCharacter(
                  fractional_part,
                  index
               );

            if(
               character < '0'
               ||
               character > '9'
            )
            {
               return false;
            }
         }
      }


      int year =
         (int)StringToInteger(
            StringSubstr(value, 0, 4)
         );

      int month =
         (int)StringToInteger(
            StringSubstr(value, 5, 2)
         );

      int day =
         (int)StringToInteger(
            StringSubstr(value, 8, 2)
         );

      int hour =
         (int)StringToInteger(
            StringSubstr(value, 11, 2)
         );

      int minute =
         (int)StringToInteger(
            StringSubstr(value, 14, 2)
         );

      int second =
         (int)StringToInteger(
            StringSubstr(value, 17, 2)
         );


      if(year < 1970)
         return false;

      if(month < 1 || month > 12)
         return false;

      if(day < 1 || day > 31)
         return false;

      if(hour < 0 || hour > 23)
         return false;

      if(minute < 0 || minute > 59)
         return false;

      if(second < 0 || second > 59)
         return false;


      MqlDateTime parsed;

      parsed.year = year;
      parsed.mon = month;
      parsed.day = day;
      parsed.hour = hour;
      parsed.min = minute;
      parsed.sec = second;
      parsed.day_of_week = 0;
      parsed.day_of_year = 0;


      datetime parsed_time =
         StructToTime(parsed);

      if(parsed_time <= 0)
         return false;


      MqlDateTime verified;

      TimeToStruct(
         parsed_time,
         verified
      );

      if(
         verified.year != year
         ||
         verified.mon != month
         ||
         verified.day != day
         ||
         verified.hour != hour
         ||
         verified.min != minute
         ||
         verified.sec != second
      )
      {
         return false;
      }


      result =
         parsed_time;

      return true;
   }
};


#endif
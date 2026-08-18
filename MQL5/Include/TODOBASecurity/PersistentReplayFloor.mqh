#ifndef TODOBA_PERSISTENT_REPLAY_FLOOR_MQH
#define TODOBA_PERSISTENT_REPLAY_FLOOR_MQH


class TODOBAPersistentReplayFloor
{
private:

   string state_file_name;
   string temp_file_name;

   string security_domain;
   string agent_id;
   string account_fingerprint;

   long last_security_sequence;

   bool configured;
   bool ready;


public:

   TODOBAPersistentReplayFloor()
   {
      state_file_name = "";
      temp_file_name = "";

      security_domain = "";
      agent_id = "";
      account_fingerprint = "";

      last_security_sequence = 0;

      configured = false;
      ready = false;
   }


   bool Configure(
      const string file_name,
      const string domain,
      const string expected_agent_id,
      const string expected_account_fingerprint
   )
   {
      if(StringLen(file_name) == 0)
         return false;

      if(StringLen(domain) == 0)
         return false;

      if(StringLen(expected_agent_id) == 0)
         return false;

      if(
         StringLen(
            expected_account_fingerprint
         ) == 0
      )
      {
         return false;
      }

      state_file_name =
         file_name;

      temp_file_name =
         file_name
         + ".tmp";

      security_domain =
         domain;

      agent_id =
         expected_agent_id;

      account_fingerprint =
         expected_account_fingerprint;

      last_security_sequence = 0;

      configured = true;
      ready = false;

      return true;
   }


   bool Restore()
   {
      ready = false;
      last_security_sequence = 0;

      if(!configured)
         return false;

      if(
         !FileIsExist(
            state_file_name
         )
      )
      {
         return false;
      }

      ResetLastError();

      int file_handle =
         FileOpen(
            state_file_name,
            FILE_READ
            |
            FILE_BIN
         );

      if(
         file_handle
         ==
         INVALID_HANDLE
      )
      {
         return false;
      }

      string stored_magic = "";

      if(
         !ReadStringField(
            file_handle,
            stored_magic
         )
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }

      if(
         stored_magic
         !=
         "TODOBA_REPLAY_FLOOR_V1"
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }


      string stored_domain = "";

      if(
         !ReadStringField(
            file_handle,
            stored_domain
         )
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }

      if(
         stored_domain
         !=
         security_domain
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }


      string stored_agent_id = "";

      if(
         !ReadStringField(
            file_handle,
            stored_agent_id
         )
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }

      if(
         stored_agent_id
         !=
         agent_id
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }


      string stored_account_fingerprint = "";

      if(
         !ReadStringField(
            file_handle,
            stored_account_fingerprint
         )
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }

      if(
         stored_account_fingerprint
         !=
         account_fingerprint
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }


      long remaining_bytes =
         (long)FileSize(
            file_handle
         )
         -
         (long)FileTell(
            file_handle
         );

      if(
         remaining_bytes
         !=
         8
      )
      {
         FileClose(
            file_handle
         );

         return false;
      }


      long stored_security_sequence =
         FileReadLong(
            file_handle
         );

      FileClose(
         file_handle
      );

      if(
         stored_security_sequence
         <
         0
      )
      {
         return false;
      }


      last_security_sequence =
         stored_security_sequence;

      ready = true;

      return true;
   }


   bool Bootstrap(
      const long security_sequence
   )
   {
      if(!configured)
         return false;

      if(security_sequence < 0)
         return false;

      ready = false;
      last_security_sequence = 0;

      if(
         !Persist(
            security_sequence
         )
      )
      {
         return false;
      }

      last_security_sequence =
         security_sequence;

      ready = true;

      return true;
   }


   bool Check(
      const long security_sequence
   )
   {
      if(!ready)
         return false;

      if(security_sequence <= 0)
         return false;

      if(
         security_sequence
         <=
         last_security_sequence
      )
      {
         return false;
      }

      return true;
   }


   bool Commit(
      const long security_sequence
   )
   {
      if(
         !Check(
            security_sequence
         )
      )
      {
         return false;
      }

      if(
         !Persist(
            security_sequence
         )
      )
      {
         return false;
      }

      last_security_sequence =
         security_sequence;

      return true;
   }


   bool IsReady()
   {
      return ready;
   }


   long LastSecuritySequence()
   {
      return last_security_sequence;
   }


private:

   bool Persist(
      const long security_sequence
   )
   {
      if(!configured)
         return false;

      if(security_sequence < 0)
         return false;


      if(
         FileIsExist(
            temp_file_name
         )
      )
      {
         if(
            !FileDelete(
               temp_file_name
            )
         )
         {
            return false;
         }
      }


      ResetLastError();

      int file_handle =
         FileOpen(
            temp_file_name,
            FILE_WRITE
            |
            FILE_BIN
         );

      if(
         file_handle
         ==
         INVALID_HANDLE
      )
      {
         return false;
      }


      bool write_succeeded = true;

      if(
         !WriteStringField(
            file_handle,
            "TODOBA_REPLAY_FLOOR_V1"
         )
      )
      {
         write_succeeded = false;
      }

      if(
         write_succeeded
         &&
         !WriteStringField(
            file_handle,
            security_domain
         )
      )
      {
         write_succeeded = false;
      }

      if(
         write_succeeded
         &&
         !WriteStringField(
            file_handle,
            agent_id
         )
      )
      {
         write_succeeded = false;
      }

      if(
         write_succeeded
         &&
         !WriteStringField(
            file_handle,
            account_fingerprint
         )
      )
      {
         write_succeeded = false;
      }

      if(
         write_succeeded
         &&
         FileWriteLong(
            file_handle,
            security_sequence
         )
         !=
         8
      )
      {
         write_succeeded = false;
      }


      if(write_succeeded)
      {
         FileFlush(
            file_handle
         );
      }

      FileClose(
         file_handle
      );


      if(!write_succeeded)
      {
         FileDelete(
            temp_file_name
         );

         return false;
      }


      ResetLastError();

      if(
         !FileMove(
            temp_file_name,
            0,
            state_file_name,
            FILE_REWRITE
         )
      )
      {
         FileDelete(
            temp_file_name
         );

         return false;
      }


      return true;
   }


   bool WriteStringField(
      const int file_handle,
      const string value
   )
   {
      int length =
         StringLen(
            value
         );

      if(length <= 0)
         return false;

      if(
         FileWriteInteger(
            file_handle,
            length,
            INT_VALUE
         )
         !=
         4
      )
      {
         return false;
      }

      uint expected_bytes =
         (uint)(
            length
            *
            2
         );

      uint written_bytes =
         FileWriteString(
            file_handle,
            value,
            length
         );

      if(
         written_bytes
         !=
         expected_bytes
      )
      {
         return false;
      }

      return true;
   }


   bool ReadStringField(
      const int file_handle,
      string &value
   )
   {
      long remaining_before_length =
         (long)FileSize(
            file_handle
         )
         -
         (long)FileTell(
            file_handle
         );

      if(
         remaining_before_length
         <
         4
      )
      {
         return false;
      }


      int length =
         FileReadInteger(
            file_handle,
            INT_VALUE
         );

      if(
         length <= 0
         ||
         length > 1024
      )
      {
         return false;
      }


      long required_bytes =
         (long)length
         *
         2;

      long remaining_before_string =
         (long)FileSize(
            file_handle
         )
         -
         (long)FileTell(
            file_handle
         );

      if(
         remaining_before_string
         <
         required_bytes
      )
      {
         return false;
      }


      value =
         FileReadString(
            file_handle,
            length
         );

      if(
         StringLen(
            value
         )
         !=
         length
      )
      {
         return false;
      }

      return true;
   }
};


#endif
#ifndef TODOBA_EXECUTION_MISSION_SIGNATURE_VERIFIER_MQH
#define TODOBA_EXECUTION_MISSION_SIGNATURE_VERIFIER_MQH


#include <TODOBAExecution/ExecutionMissionParser.mqh>
#include <TODOBAExecution/ExecutionMissionSigningPayload.mqh>


class TODOBAExecutionMissionSignatureVerifier
{
private:

   static string BytesToHex(
      const uchar &bytes[]
   )
   {
      string result = "";

      for(int i = 0; i < ArraySize(bytes); i++)
      {
         result += StringFormat(
            "%02x",
            bytes[i]
         );
      }

      return result;
   }


   static bool Sha256(
      const uchar &data[],
      uchar &digest[]
   )
   {
      uchar key[];

      ArrayResize(
         key,
         0
      );

      int result = CryptEncode(
         CRYPT_HASH_SHA256,
         data,
         key,
         digest
      );

      return result > 0;
   }


   static bool HmacSha256(
      const string secret,
      const string payload,
      string &signature
   )
   {
      const int block_size = 64;

      uchar key_bytes[];

      StringToCharArray(
         secret,
         key_bytes,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

      if(ArraySize(key_bytes) > 0)
      {
         ArrayResize(
            key_bytes,
            ArraySize(key_bytes) - 1
         );
      }

      if(ArraySize(key_bytes) > block_size)
      {
         uchar hashed_key[];

         if(
            !Sha256(
               key_bytes,
               hashed_key
            )
         )
         {
            return false;
         }

         ArrayResize(
            key_bytes,
            ArraySize(hashed_key)
         );

         ArrayCopy(
            key_bytes,
            hashed_key
         );
      }

      uchar padded_key[];

      ArrayResize(
         padded_key,
         block_size
      );

      ArrayInitialize(
         padded_key,
         0
      );

      for(
         int i = 0;
         i < ArraySize(key_bytes);
         i++
      )
      {
         padded_key[i] = key_bytes[i];
      }

      uchar inner_pad[];
      uchar outer_pad[];

      ArrayResize(
         inner_pad,
         block_size
      );

      ArrayResize(
         outer_pad,
         block_size
      );

      for(int i = 0; i < block_size; i++)
      {
         inner_pad[i] = (
            padded_key[i] ^ 0x36
         );

         outer_pad[i] = (
            padded_key[i] ^ 0x5c
         );
      }

      uchar payload_bytes[];

      StringToCharArray(
         payload,
         payload_bytes,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

      if(ArraySize(payload_bytes) > 0)
      {
         ArrayResize(
            payload_bytes,
            ArraySize(payload_bytes) - 1
         );
      }

      uchar inner_data[];

      ArrayResize(
         inner_data,
         block_size
         + ArraySize(payload_bytes)
      );

      ArrayCopy(
         inner_data,
         inner_pad,
         0,
         0,
         block_size
      );

      ArrayCopy(
         inner_data,
         payload_bytes,
         block_size,
         0,
         ArraySize(payload_bytes)
      );

      uchar inner_hash[];

      if(
         !Sha256(
            inner_data,
            inner_hash
         )
      )
      {
         return false;
      }

      uchar outer_data[];

      ArrayResize(
         outer_data,
         block_size
         + ArraySize(inner_hash)
      );

      ArrayCopy(
         outer_data,
         outer_pad,
         0,
         0,
         block_size
      );

      ArrayCopy(
         outer_data,
         inner_hash,
         block_size,
         0,
         ArraySize(inner_hash)
      );

      uchar final_hash[];

      if(
         !Sha256(
            outer_data,
            final_hash
         )
      )
      {
         return false;
      }

      signature = BytesToHex(
         final_hash
      );

      return true;
   }


public:

   static bool Verify(
      TODOBAExecutionMission &mission,
      const string supplied_signature,
      const string signing_secret
   )
   {
      if(StringLen(supplied_signature) == 0)
         return false;

      if(StringLen(signing_secret) == 0)
         return false;

      string payload =
         TODOBAExecutionMissionSigningPayload::Build(
            mission
         );

      string expected_signature = "";

      if(
         !HmacSha256(
            signing_secret,
            payload,
            expected_signature
         )
      )
      {
         return false;
      }

      string normalized_supplied =
         supplied_signature;

      string normalized_expected =
         expected_signature;

      StringToLower(
         normalized_supplied
      );

      StringToLower(
         normalized_expected
      );

      return (
         StringCompare(
            normalized_supplied,
            normalized_expected
         ) == 0
      );
   }


   static bool SignForProof(
      TODOBAExecutionMission &mission,
      const string signing_secret,
      string &signature
   )
   {
      string payload =
         TODOBAExecutionMissionSigningPayload::Build(
            mission
         );

      return HmacSha256(
         signing_secret,
         payload,
         signature
      );
   }
};


#endif
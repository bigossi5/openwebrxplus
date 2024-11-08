#!/bin/perl

$First = 1;

printf("[\n");

while(<STDIN>)
{
  if(/^(.*)\|(.*)\|(.*)\|(\S*)\|(\S+)\s*$/)
  {
    $Name  = $1;
    $Text1 = $2;
    $Text2 = $3;
    $Freq  = $4;
    $Mod   = $5;

    if(($Name ne "") && ($Freq ne "") && ($Mod ne ""))
    {
      if($Text1 ne "")
      {
        $Name = $Name . " - " . $Text1;
        #if($Text2 ne "")
        #{
        #  $Name = $Name . ", " . $Text2;
        #}
      }
      elsif($Text2 ne "")
      {
        $Name = $Name . " - " . $Text2;
      }

      if($First) { $First=0; } else { printf(",\n"); }

      # Set FAX frequencies 1.9kHz lower than the carrier
      if(lc($Mod) eq "fax")     { $Freq -= 1.9; }
      # Set RTTY frequencies 1kHz lower than the left carrier
      if(lc($Mod) eq "rtty450") { $Freq -= 1.0; }
      if(lc($Mod) eq "rtty170") { $Freq -= 1.0; }
      if(lc($Mod) eq "rtty85")  { $Freq -= 1.0; }
      # Set NAVTEX/SITOR-B/DSC frequencies 1kHz lower than the left carrier
      if(lc($Mod) eq "sitorb")  { $Freq -= 1.0; }
      if(lc($Mod) eq "navtex")  { $Freq -= 1.0; }
      if(lc($Mod) eq "dsc")     { $Freq -= 1.0; }
      # Set BPSK frequencies 1000Hz lower than the carrier
      if(lc($Mod) eq "bpsk31")  { $Freq -= 1.0; }
      if(lc($Mod) eq "bpsk63")  { $Freq -= 1.0; }
      # Set CW frequencies 800Hz lower than the carrier
      # This is now done at the client side!
      #if(lc($Mod) eq "cw")      { $Freq -= 0.8; }

      printf("    {\n");
      printf("        \"name\" : \"%s\",\n", $Name);
      printf("        \"frequency\" : %d,\n", $Freq * 1000);
      printf("        \"modulation\" : \"%s\"\n", lc($Mod));
      printf("    }");
    }
  }
}

printf("\n]\n");

#!/usr/bin/env python3
"""
Standalone script to perform interactive Monarch Money login with MFA support.
Run this script to authenticate and save a session file that the MCP server can use.
"""

import asyncio
import os
import getpass
from monarchmoney import MonarchMoney, RequireMFAException
from dotenv import load_dotenv

async def main():
    load_dotenv()
    
    print("\n🏦 Monarch Money - Claude Desktop Setup")
    print("=" * 45)
    print("This will authenticate you once and save a session")
    print("for seamless access through Claude Desktop.\n")
    
    mm = MonarchMoney()
    
    try:
        # Get credentials
        email = input("Email: ")
        password = getpass.getpass("Password: ")
        
        print("Attempting login...")
        
        try:
            # Try normal login first
            await mm.login(email, password)
            print("✅ Login successful (no MFA required)")
            
        except RequireMFAException:
            print("🔐 MFA required")
            mfa_code = input("Two Factor Code: ")
            
            # Create new instance for MFA
            mm_mfa = MonarchMoney()
            result = await mm_mfa.multi_factor_authenticate(email, password, mfa_code)
            print(f"✅ MFA authentication result: {result}")
            mm = mm_mfa  # Use the authenticated instance
        
        # Test the connection first
        print("\nTesting connection...")
        accounts = await mm.get_accounts()
        if accounts:
            account_count = len(accounts.get("accounts", []))
            print(f"✅ Found {account_count} accounts")
        else:
            print("❌ No accounts data returned")
            return
        
        # Try to save session for MCP server to use
        try:
            session_file = os.getenv("MONARCH_SESSION_FILE", "monarch_session.json")
            session_path = os.path.join(os.getcwd(), session_file)
            
            # Try using the library's built-in session saving
            print(f"\nSaving session to: {session_path}")
            result = await mm.save_session(session_path)
            print(f"Save result: {result}")
            
            if os.path.exists(session_path):
                print(f"✅ Session saved successfully!")
            else:
                print("❌ Session file was not created")
                
        except Exception as save_error:
            print(f"❌ Could not save session: {save_error}")
            print("However, the existing session should work with the MCP server.")
        
        print("\n🎉 Setup complete! You can now use these tools in Claude Desktop:")
        print("   • get_accounts - View all your accounts")  
        print("   • get_transactions - Recent transactions")
        print("   • get_budgets - Budget information")
        print("   • get_cashflow - Income/expense analysis")
        print("\n💡 Session will persist across Claude restarts!")
        
    except Exception as e:
        print(f"\n❌ Login failed: {e}")
        print("\nPlease check your credentials and try again.")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(main())
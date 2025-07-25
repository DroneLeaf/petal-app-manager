"""
Example showing how to use both LocalDBProxy and CloudDBProxy
"""
import asyncio
import os
from petal_app_manager.proxies import LocalDBProxy, CloudDBProxy

async def example_usage():
    """
    Example showing how to use both proxies with the same interface,
    except that CloudDBProxy requires machine_id to be passed to each method.
    """
    
    # Setup LocalDB proxy
    local_proxy = LocalDBProxy(host="localhost", port=3000, debug=True)
    await local_proxy.start()
    
    try:
        # LocalDB operations (machine_id is retrieved automatically)
        local_result = await local_proxy.get_item(
            table_name="config-robot_instances",
            partition_key="id",
            partition_value="some-robot-id"
        )
        print(f"Local result: {local_result}")
        
        # Scan items locally
        local_items = await local_proxy.scan_items(
            table_name="config-robot_instances"
        )
        print(f"Local items: {local_items}")
        
    finally:
        await local_proxy.stop()
    
    # Setup CloudDB proxy (only if environment variables are configured)
    if os.environ.get('ACCESS_TOKEN_URL') and os.environ.get('CLOUD_ENDPOINT'):
        cloud_proxy = CloudDBProxy(debug=True)
        await cloud_proxy.start()
        
        try:
            # CloudDB operations (machine_id must be passed explicitly)
            machine_id = "your-machine-id-here"  # Get this from somewhere
            
            cloud_result = await cloud_proxy.get_item(
                table_name="config-robot_instances",
                partition_key="id",
                partition_value="some-robot-id",
                machine_id=machine_id
            )
            print(f"Cloud result: {cloud_result}")
            
            # Scan items in cloud
            cloud_items = await cloud_proxy.scan_items(
                table_name="config-robot_instances",
                machine_id=machine_id
            )
            print(f"Cloud items: {cloud_items}")
            
            # Update an item in cloud
            update_result = await cloud_proxy.update_item(
                table_name="config-robot_instances",
                filter_key="id",
                filter_value="some-robot-id",
                data={"status": "updated", "last_sync": "2025-01-24"},
                machine_id=machine_id
            )
            print(f"Cloud update result: {update_result}")
            
            # Soft delete an item in cloud
            delete_result = await cloud_proxy.delete_item(
                table_name="config-robot_instances",
                filter_key="id",
                filter_value="some-robot-id",
                machine_id=machine_id
            )
            print(f"Cloud delete result: {delete_result}")
            
        finally:
            await cloud_proxy.stop()
    else:
        print("Cloud proxy not configured - set ACCESS_TOKEN_URL and CLOUD_ENDPOINT environment variables")

if __name__ == "__main__":
    asyncio.run(example_usage())

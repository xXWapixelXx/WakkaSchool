import discord
from discord.ext import commands, tasks
import requests
from ics import Calendar
import googlemaps
from discord import Embed
import pytz
import os
import json
from datetime import datetime, timedelta


bot_token = 'MTIwMTgzMjQ1MjQ0MDQ2NTU0OA.GLZ7c_.XURKk5fLIc_kbY--bRXxAl_I6_xqLJJz-tZ38A'
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
gmaps = googlemaps.Client(key='AIzaSyBv-okHb3qFfh4DKyel1Y01NaE1BMyYVxk')

previous_schedules = {}

def fetch_ical_data(url):
    response = requests.get(url)
    return response.text

def parse_ical_data(ical_data):
    try:
        calendar = Calendar(ical_data)
        return calendar.events
    except Exception as e:
        print(f"Error parsing iCal data: {e}")
        return None

@bot.event
async def on_ready():
    print("Bot is running!")

@bot.command()
async def rooster(ctx):
    with open('config.json') as f:
        config = json.load(f)
    today = datetime.now().date()
    events = None
    for url in config['urls']:
        ical_data = fetch_ical_data(url)
        events = parse_ical_data(ical_data)
        if events:
            break
    if events:
        today_events = [event for event in events if event.begin.date() == today]
        if today_events:
            embed = Embed(title="📅 Today's Schedule 📅", color=0x00ff00)
            for event in today_events:
                embed.add_field(name=event.name, value=event.begin.strftime('%H:%M'), inline=False)
            await ctx.send(embed=embed)
            await ctx.send("Do you want to see tomorrow's schedule? If yes, type `!yes`.")
        else:
            await ctx.send("No events today.")
    else:
        await ctx.send("Error fetching or parsing iCal data.")

@bot.command()
async def yes(ctx):
    with open('config.json') as f:
        config = json.load(f)
    tomorrow = datetime.now().date() + timedelta(days=1)
    events = None
    for url in config['urls']:
        ical_data = fetch_ical_data(url)
        events = parse_ical_data(ical_data)
        if events:
            break
    if events:
        tomorrow_events = [event for event in events if event.begin.date() == tomorrow]
        if tomorrow_events:
            embed = Embed(title="📅 Tomorrow's Schedule 📅", color=0x00ff00)
            for event in tomorrow_events:
                embed.add_field(name=event.name, value=event.begin.strftime('%H:%M'), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("No events tomorrow.")
    else:
        await ctx.send("Error fetching or parsing iCal data.")

@tasks.loop(hours=6)  # Controleer elke 6 uur
async def send_schedule():
    with open('config.json') as f:
        config = json.load(f)
    for url in config['urls']:
        ical_data = fetch_ical_data(url)
        events = parse_ical_data(ical_data)
        if events:
            channel = bot.get_channel(config['schedule_channel_id'])
            current_schedule = {event.name: event.begin for event in events}
            # Load the previous schedule from a file
            if os.path.exists('previous_schedule.json'):
                with open('previous_schedule.json', 'r') as f:
                    previous_schedule = json.load(f)
                # Compare the previous schedule with the current one
                if current_schedule != previous_schedule:
                    # If there are changes, send a message to the channel
                    await channel.send("The schedule has changed.")
            # And update the previous schedule file
            with open('previous_schedule.json', 'w') as f:
                json.dump(current_schedule, f)
        else:
            print("Error fetching or parsing iCal data.")


@bot.command()
async def route(ctx, *, address):
    # Determine the destination and start time based on the schedule
    with open('config.json') as f:
        config = json.load(f)
    destination = None
    start_time = None
    for url in config['urls']:
        ical_data = fetch_ical_data(url)
        events = parse_ical_data(ical_data)
        if events:
            for event in events:
                if event.begin.date() == datetime.now().date() + timedelta(days=1):
                    if "GVP" in event.name or "Projectweek MICT1 - SWD" in event.name:
                        destination = "Groen van Prinsterersingel 52"
                    elif event.name.startswith("VDPDIF"):
                        destination = "Bleiswijkseweg 37E"
                    start_time = event.begin
                    break
    if destination is None or start_time is None:
        await ctx.send("Could not determine school location or start time from schedule.")
        return

    # Use Google Maps Directions API to get transit directions
    directions_result = gmaps.directions(address,
                                         destination,
                                         departure_time=start_time,  # Use the start time from the schedule
                                         mode="transit")

    if directions_result:
        steps = directions_result[0]['legs'][0]['steps']
        embed = Embed(title=f"🚌 Route Information for {start_time.strftime('%H:%M')} 🚌", color=0x00ff00)  # Include the start time in the title
        for step in steps:
            if step['travel_mode'] == 'TRANSIT':
                departure_time = datetime.strptime(step['transit_details']['departure_time']['text'].replace('\u202f', ' ').replace(' ', '').upper(), '%I:%M%p').time()
                embed.add_field(name="🚌 Transit", value=f"Take {step['transit_details']['line']['name']} from {step['transit_details']['departure_stop']['name']} to {step['transit_details']['arrival_stop']['name']} at {departure_time}", inline=False)
            elif step['travel_mode'] == 'WALKING':
                departure_time = (start_time + timedelta(minutes=int(step['duration']['text'].split()[0]))).strftime('%H:%M')  # Calculate the departure time for walking steps
                embed.add_field(name="🚶‍♂️ Walking", value=f"Walk for {step['duration']['text']} starting at {departure_time}", inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("No transit directions found.")

bot.run(bot_token)
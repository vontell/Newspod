-- Supabase Database Schema for Newspod Server
-- Run these SQL commands in your Supabase SQL editor

-- Create user_configs table to store user configurations
CREATE TABLE user_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Create generation_logs table to track podcast generations
CREATE TABLE generation_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    newsletters_found INTEGER DEFAULT 0,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX idx_user_configs_user_id ON user_configs(user_id);
CREATE INDEX idx_generation_logs_user_id ON generation_logs(user_id);
CREATE INDEX idx_generation_logs_generated_at ON generation_logs(generated_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for user_configs
CREATE POLICY "Users can view their own config" ON user_configs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own config" ON user_configs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own config" ON user_configs
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own config" ON user_configs
    FOR DELETE USING (auth.uid() = user_id);

-- Create RLS policies for generation_logs
CREATE POLICY "Users can view their own logs" ON generation_logs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service can insert logs" ON generation_logs
    FOR INSERT WITH CHECK (true); -- Allow server to insert logs

-- Create a trigger to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_configs_updated_at
    BEFORE UPDATE ON user_configs
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
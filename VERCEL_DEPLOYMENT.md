# Deploy NTU Publication Aggregator to Vercel

## Prerequisites
1. GitHub account
2. Vercel account (free - sign up at vercel.com)
3. Git installed on your computer

## Step 1: Prepare Your Project

Already done! Your project now has:
- ✅ `vercel.json` - Vercel configuration
- ✅ `api/index.py` - Serverless function entry point
- ✅ `requirements.txt` - Python dependencies
- ✅ `.gitignore` - Excludes unnecessary files

## Step 2: Push to GitHub

### If you don't have a Git repository yet:

```bash
# Initialize git (if not already done)
cd /Users/shubhamjariwala/Documents/ntu_project
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - NTU Publication Aggregator"

# Create a new repository on GitHub.com
# Then link it:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### If you already have a Git repository:

```bash
cd /Users/shubhamjariwala/Documents/ntu_project
git add .
git commit -m "Add Vercel deployment configuration"
git push
```

## Step 3: Deploy to Vercel

### Option A: Using Vercel Website (Easiest)

1. Go to https://vercel.com
2. Click "Sign Up" or "Login" (use GitHub for easy integration)
3. Click "Add New Project"
4. Import your GitHub repository
5. Vercel will auto-detect it's a Python project
6. Click "Deploy"
7. Wait 1-2 minutes for deployment
8. You'll get a URL like: `https://your-project-name.vercel.app`

### Option B: Using Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy (run from project directory)
cd /Users/shubhamjariwala/Documents/ntu_project
vercel

# Follow the prompts:
# - Set up and deploy? Y
# - Which scope? (choose your account)
# - Link to existing project? N
# - What's your project's name? (e.g., ntu-publications)
# - In which directory is your code located? ./
# - Want to override settings? N

# For production deployment:
vercel --prod
```

## Step 4: Configure Environment (if needed)

If you need environment variables:
1. Go to your project on Vercel dashboard
2. Click "Settings" → "Environment Variables"
3. Add any required variables
4. Redeploy

## Step 5: Custom Domain (Optional)

1. Go to your project settings on Vercel
2. Click "Domains"
3. Add your custom domain
4. Follow DNS configuration instructions

## Troubleshooting

### Issue: Build fails
**Solution:** Check that `requirements.txt` has all dependencies

### Issue: 404 errors
**Solution:** Make sure `vercel.json` routes are correct

### Issue: Import errors
**Solution:** Check that `api/index.py` correctly imports your app

### Issue: File upload doesn't work
**Solution:** Vercel has file size limits. For large Excel files, consider:
- Using Vercel Blob storage
- Or switch to Render.com (better for file uploads)

## Limitations of Vercel for This Project

⚠️ **Important Notes:**
- Vercel serverless functions have a 50MB deployment size limit
- Execution timeout: 10 seconds (free), 60 seconds (pro)
- File uploads work but have size limits
- No persistent storage (uploaded files are temporary)

## Alternative: Use Render.com Instead

If you encounter issues with Vercel (especially with file uploads), **Render.com is better suited** for this Flask app:

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your repository
5. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Click "Create Web Service"

Render advantages:
- Better for Flask apps with file uploads
- Persistent storage options
- Longer execution times
- More generous free tier for compute

## Your Deployed App

Once deployed, share your URL:
- Vercel: `https://your-app.vercel.app`
- Custom domain: `https://yourdomain.com`

Anyone with the link can access the publication aggregator!

## Updating Your Deployment

After making changes:
```bash
git add .
git commit -m "Update description"
git push
```

Vercel automatically redeploys on every push to main branch!

## Support

- Vercel Docs: https://vercel.com/docs
- Vercel Python: https://vercel.com/docs/functions/serverless-functions/runtimes/python
- Community: https://github.com/vercel/community

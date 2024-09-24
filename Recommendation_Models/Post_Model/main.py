<<<<<<< HEAD
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import tensorflow as tf
from tensorflow.keras import layers, Model
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import io
import os

############################################# LOADING, LABELLING & SPLITTING DATA ##########################################

# Set up file paths
data_folder = os.path.join(os.path.dirname(__file__), 'data')
users_csv_path = os.path.join(data_folder, 'users.csv')
saved_posts_csv_path = os.path.join(data_folder, 'saved_posts.csv')
posts_csv_path = os.path.join(data_folder, 'posts.csv')

# Load data
users_df = pd.read_csv(users_csv_path)
saved_posts_df = pd.read_csv(saved_posts_csv_path)
posts_df = pd.read_csv(posts_csv_path)

# Encode user and post IDs
user_encoder = LabelEncoder()
post_encoder = LabelEncoder()

# Ensure post_encoder is fit on all post IDs from posts_df
post_encoder.fit(posts_df['id'])

saved_posts_df['userId'] = user_encoder.fit_transform(saved_posts_df['userid'])
saved_posts_df['postId'] = post_encoder.transform(saved_posts_df['postid'])

num_users = len(user_encoder.classes_)
num_posts = len(post_encoder.classes_)

# Tokenize post titles and descriptions
tokenizer = Tokenizer()
posts_df['text'] = posts_df['title'] + " " + posts_df['caption']
tokenizer.fit_on_texts(posts_df['text'])
vocab_size = len(tokenizer.word_index) + 1

# Convert text to sequences
posts_df['text_seq'] = tokenizer.texts_to_sequences(posts_df['text'])
max_seq_length = max(posts_df['text_seq'].apply(len))
post_text_sequences = pad_sequences(posts_df['text_seq'], maxlen=max_seq_length)

# Split data into training and testing sets
train_data, test_data = train_test_split(saved_posts_df, test_size=0.2, random_state=42)

############################################# TRAINING DATA ######################################################

# Extract features and labels for training
train_user_data = train_data['userId'].values
train_post_data = train_data['postId'].values
train_post_text = post_text_sequences[train_post_data]

# Create labels for positive interactions (saved posts) and non-interactions
train_labels = np.ones(len(train_data))

# Add some negative samples (non-interactions)
num_negative_samples = len(train_data) // 2
negative_samples = train_data.sample(num_negative_samples, random_state=42)
negative_samples['id'] = 0  # Label non-interactions as 0
train_data_combined = pd.concat([train_data, negative_samples], axis=0)

train_user_data_combined = train_data_combined['userId'].values
train_post_data_combined = train_data_combined['postId'].values
train_post_text_combined = post_text_sequences[train_post_data_combined]

train_labels_combined = np.concatenate([train_labels, np.zeros(num_negative_samples)])

############################################# TESTING DATA ######################################################

# Testing data preparation
test_user_data = test_data['userId'].values
test_post_data = test_data['postId'].values
test_post_text = post_text_sequences[test_post_data]

# Create labels for positive interactions and non-interactions
test_labels = np.ones(len(test_data))

# Add some negative samples (non-interactions)
num_negative_samples_test = len(test_data) // 2
negative_samples_test = test_data.sample(num_negative_samples_test, random_state=42)
negative_samples_test['id'] = 0
test_data_combined = pd.concat([test_data, negative_samples_test], axis=0)

test_user_data_combined = test_data_combined['userId'].values
test_post_data_combined = test_data_combined['postId'].values
test_post_text_combined = post_text_sequences[test_post_data_combined]

test_labels_combined = np.concatenate([test_labels, np.zeros(num_negative_samples_test)])

############################################# SETTING UP THE MODEL ######################################################

embedding_size = 50

user_input = layers.Input(shape=(1,), name='user_input')
post_input = layers.Input(shape=(1,), name='post_input')
text_input = layers.Input(shape=(max_seq_length,), name='text_input')

user_embedding = layers.Embedding(input_dim=num_users, output_dim=embedding_size, name='user_embedding')(user_input)
post_embedding = layers.Embedding(input_dim=num_posts, output_dim=embedding_size, name='post_embedding')(post_input)

text_embedding = layers.Embedding(input_dim=vocab_size, output_dim=embedding_size, name='text_embedding')(text_input)
text_vec = layers.GlobalAveragePooling1D()(text_embedding)

user_vec = layers.Flatten()(user_embedding)
post_vec = layers.Flatten()(post_embedding)

concat = layers.Concatenate()([user_vec, post_vec, text_vec])

dense = layers.Dense(128, activation='relu')(concat)
dense = layers.Dense(64, activation='relu')(dense)
output = layers.Dense(1, activation='sigmoid')(dense)

############################################# THE MODEL AND ACCURACY ######################################################

model = Model(inputs=[user_input, post_input, text_input], outputs=output)
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# Train the model
model.fit(
    [train_user_data_combined, train_post_data_combined, train_post_text_combined],
    train_labels_combined,
    epochs=10,
    batch_size=32,
    validation_split=0.2
)

# Evaluate the model
train_loss, train_accuracy = model.evaluate([train_user_data_combined, train_post_data_combined, train_post_text_combined], train_labels_combined)
print(f"Train Loss: {train_loss}, Train Accuracy: {train_accuracy}")

test_loss, test_accuracy = model.evaluate([test_user_data_combined, test_post_data_combined, test_post_text_combined], test_labels_combined)
print(f"Test Loss: {test_loss}, Test Accuracy: {test_accuracy}")

############################################# RECOMMEND POSTS ##################################################

def recommend_posts(user_id, top_n=10):
    internal_user_id = user_encoder.transform([user_id])[0]
    
    # Get the posts that the user has already saved
    saved_post_ids = saved_posts_df[saved_posts_df['userid'] == user_id]['postid'].values
    user_created_post_ids = posts_df[posts_df['userid'] == user_id]['id'].values
    
    # Get the internal post IDs for the saved posts
    saved_internal_post_ids = post_encoder.transform(saved_post_ids)
    
    # Exclude saved and user-created posts from the recommendation process
    all_internal_post_ids = np.arange(num_posts)
    unsaved_internal_post_ids = np.setdiff1d(all_internal_post_ids, np.union1d(saved_post_ids, user_created_post_ids))

    # Get the corresponding text sequences for the unsaved posts
    unsaved_post_texts = post_text_sequences[unsaved_internal_post_ids]
    
    # Predict scores for the unsaved posts for the given user
    user_data = np.array([internal_user_id] * len(unsaved_internal_post_ids))
    post_data = unsaved_internal_post_ids

    predicted_scores = model.predict([user_data, post_data, unsaved_post_texts]).flatten()
    
    # Get top N posts by score
    top_indices = np.argsort(predicted_scores)[::-1][:top_n]
    top_internal_post_ids = unsaved_internal_post_ids[top_indices]
    
    # Check if fewer than `top_n` posts were recommended
    if len(top_internal_post_ids) < top_n:
        # Select additional random posts to fill the gap
        remaining_needed = top_n - len(top_internal_post_ids)
        remaining_posts = np.setdiff1d(unsaved_internal_post_ids, top_internal_post_ids)
        if len(remaining_posts) >= remaining_needed:
            additional_post_ids = np.random.choice(remaining_posts, size=remaining_needed, replace=False)
        else:
            additional_post_ids = remaining_posts
        # Combine the top posts with the additional ones
        top_internal_post_ids = np.concatenate([top_internal_post_ids, additional_post_ids])

    # Convert internal post IDs back to original post IDs
    recommended_posts = posts_df.loc[posts_df['id'].isin(post_encoder.inverse_transform(top_internal_post_ids))]
    
    # Print the posts saved by the user
    print("\nPosts saved by the user:")
    saved_posts = posts_df.loc[posts_df['id'].isin(post_encoder.inverse_transform(saved_post_ids))]
    print(saved_posts[['title', 'caption']])

    print("\nPosts created by the user:")
    created_posts = posts_df.loc[posts_df['id'].isin(user_created_post_ids)]
    print(created_posts[['title', 'caption']])

    print("\nRecommended posts:")
    print(recommended_posts[['title', 'caption']])

    return recommended_posts


# Example: Recommend posts for user with ID 1
recommended_posts = recommend_posts(user_id=102, top_n=10)

# Save the model
model.save('post_recommendation_model.keras')

# Load the model
loaded_model = tf.keras.models.load_model('post_recommendation_model.keras')
=======
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import tensorflow as tf
from tensorflow.keras import layers, Model
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
import io
import os

############################################# LOADING, LABELLING & SPLITTING DATA ##########################################

# Set up file paths
data_folder = os.path.join(os.path.dirname(__file__), 'data')
users_csv_path = os.path.join(data_folder, 'users.csv')
saved_posts_csv_path = os.path.join(data_folder, 'saved_posts.csv')
posts_csv_path = os.path.join(data_folder, 'posts.csv')

# Load data
users_df = pd.read_csv(users_csv_path)
saved_posts_df = pd.read_csv(saved_posts_csv_path)
posts_df = pd.read_csv(posts_csv_path)

# Encode user and post IDs
user_encoder = LabelEncoder()
post_encoder = LabelEncoder()

# Ensure post_encoder is fit on all post IDs from posts_df
post_encoder.fit(posts_df['id'])

saved_posts_df['userId'] = user_encoder.fit_transform(saved_posts_df['userid'])
saved_posts_df['postId'] = post_encoder.transform(saved_posts_df['postid'])

num_users = len(user_encoder.classes_)
num_posts = len(post_encoder.classes_)

# Tokenize post titles and descriptions
tokenizer = Tokenizer()
posts_df['text'] = posts_df['title'] + " " + posts_df['caption']
tokenizer.fit_on_texts(posts_df['text'])
vocab_size = len(tokenizer.word_index) + 1

# Convert text to sequences
posts_df['text_seq'] = tokenizer.texts_to_sequences(posts_df['text'])
max_seq_length = max(posts_df['text_seq'].apply(len))
post_text_sequences = pad_sequences(posts_df['text_seq'], maxlen=max_seq_length)

# Split data into training and testing sets
train_data, test_data = train_test_split(saved_posts_df, test_size=0.2, random_state=42)

############################################# TRAINING DATA ######################################################

# Extract features and labels for training
train_user_data = train_data['userId'].values
train_post_data = train_data['postId'].values
train_post_text = post_text_sequences[train_post_data]

# Create labels for positive interactions (saved posts) and non-interactions
train_labels = np.ones(len(train_data))

# Add some negative samples (non-interactions)
num_negative_samples = len(train_data) // 2
negative_samples = train_data.sample(num_negative_samples, random_state=42)
negative_samples['id'] = 0  # Label non-interactions as 0
train_data_combined = pd.concat([train_data, negative_samples], axis=0)

train_user_data_combined = train_data_combined['userId'].values
train_post_data_combined = train_data_combined['postId'].values
train_post_text_combined = post_text_sequences[train_post_data_combined]

train_labels_combined = np.concatenate([train_labels, np.zeros(num_negative_samples)])

############################################# TESTING DATA ######################################################

# Testing data preparation
test_user_data = test_data['userId'].values
test_post_data = test_data['postId'].values
test_post_text = post_text_sequences[test_post_data]

# Create labels for positive interactions and non-interactions
test_labels = np.ones(len(test_data))

# Add some negative samples (non-interactions)
num_negative_samples_test = len(test_data) // 2
negative_samples_test = test_data.sample(num_negative_samples_test, random_state=42)
negative_samples_test['id'] = 0
test_data_combined = pd.concat([test_data, negative_samples_test], axis=0)

test_user_data_combined = test_data_combined['userId'].values
test_post_data_combined = test_data_combined['postId'].values
test_post_text_combined = post_text_sequences[test_post_data_combined]

test_labels_combined = np.concatenate([test_labels, np.zeros(num_negative_samples_test)])

############################################# SETTING UP THE MODEL ######################################################

embedding_size = 50

user_input = layers.Input(shape=(1,), name='user_input')
post_input = layers.Input(shape=(1,), name='post_input')
text_input = layers.Input(shape=(max_seq_length,), name='text_input')

user_embedding = layers.Embedding(input_dim=num_users, output_dim=embedding_size, name='user_embedding')(user_input)
post_embedding = layers.Embedding(input_dim=num_posts, output_dim=embedding_size, name='post_embedding')(post_input)

text_embedding = layers.Embedding(input_dim=vocab_size, output_dim=embedding_size, name='text_embedding')(text_input)
text_vec = layers.GlobalAveragePooling1D()(text_embedding)

user_vec = layers.Flatten()(user_embedding)
post_vec = layers.Flatten()(post_embedding)

concat = layers.Concatenate()([user_vec, post_vec, text_vec])

dense = layers.Dense(128, activation='relu')(concat)
dense = layers.Dense(64, activation='relu')(dense)
output = layers.Dense(1, activation='sigmoid')(dense)

############################################# THE MODEL AND ACCURACY ######################################################

model = Model(inputs=[user_input, post_input, text_input], outputs=output)
model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# Train the model
model.fit(
    [train_user_data_combined, train_post_data_combined, train_post_text_combined],
    train_labels_combined,
    epochs=10,
    batch_size=32,
    validation_split=0.2
)

# Evaluate the model
train_loss, train_accuracy = model.evaluate([train_user_data_combined, train_post_data_combined, train_post_text_combined], train_labels_combined)
print(f"Train Loss: {train_loss}, Train Accuracy: {train_accuracy}")

test_loss, test_accuracy = model.evaluate([test_user_data_combined, test_post_data_combined, test_post_text_combined], test_labels_combined)
print(f"Test Loss: {test_loss}, Test Accuracy: {test_accuracy}")

############################################# RECOMMEND POSTS ##################################################

def recommend_posts(user_id, top_n=10):
    internal_user_id = user_encoder.transform([user_id])[0]
    
    # Get the posts that the user has already saved
    saved_post_ids = saved_posts_df[saved_posts_df['userid'] == user_id]['postid'].values
    user_created_post_ids = posts_df[posts_df['userid'] == user_id]['id'].values
    
    # Get the internal post IDs for the saved posts
    saved_internal_post_ids = post_encoder.transform(saved_post_ids)
    
    # Exclude saved and user-created posts from the recommendation process
    all_internal_post_ids = np.arange(num_posts)
    unsaved_internal_post_ids = np.setdiff1d(all_internal_post_ids, np.union1d(saved_post_ids, user_created_post_ids))

    # Get the corresponding text sequences for the unsaved posts
    unsaved_post_texts = post_text_sequences[unsaved_internal_post_ids]
    
    # Predict scores for the unsaved posts for the given user
    user_data = np.array([internal_user_id] * len(unsaved_internal_post_ids))
    post_data = unsaved_internal_post_ids

    predicted_scores = model.predict([user_data, post_data, unsaved_post_texts]).flatten()
    
    # Get top N posts by score
    top_indices = np.argsort(predicted_scores)[::-1][:top_n]
    top_internal_post_ids = unsaved_internal_post_ids[top_indices]
    
    # Check if fewer than `top_n` posts were recommended
    if len(top_internal_post_ids) < top_n:
        # Select additional random posts to fill the gap
        remaining_needed = top_n - len(top_internal_post_ids)
        remaining_posts = np.setdiff1d(unsaved_internal_post_ids, top_internal_post_ids)
        if len(remaining_posts) >= remaining_needed:
            additional_post_ids = np.random.choice(remaining_posts, size=remaining_needed, replace=False)
        else:
            additional_post_ids = remaining_posts
        # Combine the top posts with the additional ones
        top_internal_post_ids = np.concatenate([top_internal_post_ids, additional_post_ids])

    # Convert internal post IDs back to original post IDs
    recommended_posts = posts_df.loc[posts_df['id'].isin(post_encoder.inverse_transform(top_internal_post_ids))]
    
    # Print the posts saved by the user
    print("\nPosts saved by the user:")
    saved_posts = posts_df.loc[posts_df['id'].isin(post_encoder.inverse_transform(saved_post_ids))]
    print(saved_posts[['title', 'caption']])

    print("\nPosts created by the user:")
    created_posts = posts_df.loc[posts_df['id'].isin(user_created_post_ids)]
    print(created_posts[['title', 'caption']])

    print("\nRecommended posts:")
    print(recommended_posts[['title', 'caption']])

    return recommended_posts


# Example: Recommend posts for user with ID 1
recommended_posts = recommend_posts(user_id=102, top_n=10)

# Save the model
model.save('post_recommendation_model.keras')

# Load the model
loaded_model = tf.keras.models.load_model('post_recommendation_model.keras')
>>>>>>> e7f4930178a3c2b671abb454c5a0231e15b5e8e9
